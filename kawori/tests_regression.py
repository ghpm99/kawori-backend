import io
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings
from PIL import Image

from kawori.decorators import validate_user
from kawori.middleware import CsrfCookieOnlyMiddleware, OriginFilterMiddleware, SimpleCorsMiddleware
from kawori import utils


class KaworiUtilsRegressionTestCase(TestCase):
    def test_paginate_format_date_and_boolean(self):
        page = utils.paginate([1, 2, 3], page_number=1, per_page=2)
        self.assertEqual(page["current_page"], 1)
        self.assertEqual(page["total_pages"], 2)
        self.assertEqual(page["data"], [1, 2])

        self.assertIsNotNone(utils.format_date("2026-01-01"))
        self.assertIsNone(utils.format_date("invalid"))

        self.assertFalse(utils.boolean("0"))
        self.assertTrue(utils.boolean("1"))
        self.assertFalse(utils.boolean("false"))
        self.assertTrue(utils.boolean("true"))

    def test_image_helpers_and_glow_effect(self):
        image = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
        image_rgb = Image.new("RGB", (20, 20), (255, 255, 255))

        self.assertEqual(utils.hex_to_rgb("#112233"), (17, 34, 51))
        prepared, mask = utils._prepare_image_and_mask(image_rgb)
        self.assertEqual(prepared.mode, "RGBA")
        self.assertEqual(mask.mode, "L")

        glow = utils.apply_glowing_icon(image, hex_color="#00FF00")
        self.assertEqual(glow.mode, "RGBA")

        vivid = utils.apply_vivid_outline_glow(image, hex_color="#FF0000")
        self.assertEqual(vivid.mode, "RGBA")

        effected = utils.apply_glow_effect(image, hex_color="#ABCDEF")
        self.assertEqual(effected.mode, "RGBA")

        resized = utils._resize_to_original(Image.new("RGBA", (30, 30), (0, 0, 0, 0)), (20, 20))
        self.assertEqual(resized.size, (20, 20))

    def test_get_glowed_symbol_class_and_sprite_extractors(self):
        base_icon = Image.new("RGBA", (50, 50), (255, 255, 255, 255))

        no_file_class = SimpleNamespace(
            color="#123456",
            image=SimpleNamespace(name="", storage=SimpleNamespace(exists=lambda _: False)),
            class_order=1,
        )
        with patch("kawori.utils.apply_glow_effect", return_value=base_icon) as mocked_glow:
            result = utils.get_glowed_symbol_class(no_file_class, base_icon)
        self.assertEqual(result, base_icon)
        mocked_glow.assert_called_once()

        image_buffer = io.BytesIO()
        Image.new("RGBA", (10, 10), (10, 10, 10, 255)).save(image_buffer, format="PNG")
        image_buffer.seek(0)
        with_file_class = SimpleNamespace(
            color="#123456",
            image=SimpleNamespace(name="x.png", storage=SimpleNamespace(exists=lambda _: True), file=image_buffer),
            class_order=1,
        )
        loaded = utils.get_glowed_symbol_class(with_file_class, base_icon)
        self.assertEqual(loaded.mode, "RGBA")

        bdo_class = SimpleNamespace(class_order=1, color="#00FF00", image=with_file_class.image)
        with patch("kawori.utils.Image.open") as mocked_open, patch(
            "kawori.utils.get_glowed_symbol_class", return_value=base_icon
        ):
            mocked_open.side_effect = [
                Image.new("RGBA", (100, 100), (0, 0, 255, 255)),
                Image.new("RGBA", (100, 100), (0, 0, 255, 255)),
                Image.new("RGB", (utils.CLASS_IMAGE_SPR_PIXEL_X * 2, utils.CLASS_IMAGE_SPR_PIXEL_Y), (255, 0, 0)),
            ]
            symbol_default = utils.get_symbol_class(bdo_class, symbol_style="D")
            symbol_green = utils.get_symbol_class(bdo_class, symbol_style="G")
            class_image = utils.get_image_class(1)

        self.assertEqual(symbol_default.mode, "RGBA")
        self.assertEqual(symbol_green.mode, "RGBA")
        self.assertEqual(class_image.size, (utils.CLASS_IMAGE_SPR_PIXEL_X, utils.CLASS_IMAGE_SPR_PIXEL_Y))


class KaworiDecoratorsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="kw-user", email="kw-user@test.com", password="123", is_active=True)
        cls.admin_group = Group.objects.create(name="admin")
        cls.admin_group.user_set.add(cls.user)

    def setUp(self):
        self.rf = RequestFactory()

    def _build_access_token_mock(self, user_id):
        token = MagicMock()
        token.verify.return_value = None
        token.verify_token_type.return_value = None
        token.get.return_value = user_id
        return token

    def test_validate_user_branches(self):
        @validate_user("admin")
        def protected_view(request, user):
            return JsonResponse({"ok": True, "user": user.username})

        request = self.rf.get("/")
        response = protected_view(request)
        self.assertEqual(response.status_code, 401)

        request = self.rf.get("/")
        request.COOKIES["access_token"] = "invalid"
        with patch("kawori.decorators.settings.ACCESS_TOKEN_NAME", "access_token"), patch(
            "kawori.decorators.AccessToken", side_effect=Exception("bad")
        ):
            response = protected_view(request)
        self.assertEqual(response.status_code, 401)

        request = self.rf.get("/")
        request.COOKIES["access_token"] = "token"
        with patch("kawori.decorators.settings.ACCESS_TOKEN_NAME", "access_token"), patch(
            "kawori.decorators.AccessToken", return_value=self._build_access_token_mock(None)
        ):
            response = protected_view(request)
        self.assertEqual(response.status_code, 403)

        request = self.rf.get("/")
        request.COOKIES["access_token"] = "token"
        with patch("kawori.decorators.settings.ACCESS_TOKEN_NAME", "access_token"), patch(
            "kawori.decorators.AccessToken", return_value=self._build_access_token_mock(self.user.id)
        ), patch("kawori.decorators.User.objects.get", side_effect=User.DoesNotExist):
            response = protected_view(request)
        self.assertEqual(response.status_code, 403)

        inactive = User.objects.create_user(username="inactive-kw", password="123", is_active=False)
        request = self.rf.get("/")
        request.COOKIES["access_token"] = "token"
        with patch("kawori.decorators.settings.ACCESS_TOKEN_NAME", "access_token"), patch(
            "kawori.decorators.AccessToken", return_value=self._build_access_token_mock(inactive.id)
        ):
            response = protected_view(request)
        self.assertEqual(response.status_code, 403)

        no_perm_user = User.objects.create_user(username="no-perm-kw", password="123", is_active=True)
        request = self.rf.get("/")
        request.COOKIES["access_token"] = "token"
        with patch("kawori.decorators.settings.ACCESS_TOKEN_NAME", "access_token"), patch(
            "kawori.decorators.AccessToken", return_value=self._build_access_token_mock(no_perm_user.id)
        ):
            response = protected_view(request)
        self.assertEqual(response.status_code, 403)

        request = self.rf.get("/")
        request.COOKIES["access_token"] = "token"
        with patch("kawori.decorators.settings.ACCESS_TOKEN_NAME", "access_token"), patch(
            "kawori.decorators.AccessToken", return_value=self._build_access_token_mock(self.user.id)
        ):
            response = protected_view(request)
        self.assertEqual(response.status_code, 200)


@override_settings(BASE_URL="http://api.local", BASE_URL_FRONTEND_LIST=["http://front.local", "https://app.local"])
class KaworiMiddlewareRegressionTestCase(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_csrf_cookie_only_and_simple_cors(self):
        csrf_mw = CsrfCookieOnlyMiddleware(get_response=lambda r: JsonResponse({}))
        request = self.rf.get("/")
        request.COOKIES["csrftoken"] = "abc"
        csrf_mw.process_request(request)
        self.assertEqual(request.META["HTTP_X_CSRFTOKEN"], "abc")

        cors = SimpleCorsMiddleware(get_response=lambda r: JsonResponse({}))
        req_options_allowed = self.rf.options("/", HTTP_ORIGIN="http://front.local")
        preflight = cors.process_request(req_options_allowed)
        self.assertIsNotNone(preflight)
        self.assertEqual(preflight["Access-Control-Allow-Origin"], "http://front.local")

        req_options_denied = self.rf.options("/", HTTP_ORIGIN="http://evil.local")
        self.assertIsNone(cors.process_request(req_options_denied))

        req_resp_allowed = self.rf.get("/", HTTP_ORIGIN="https://app.local")
        response = cors.process_response(req_resp_allowed, JsonResponse({}))
        self.assertEqual(response["Access-Control-Allow-Origin"], "https://app.local")

        req_resp_denied = self.rf.get("/", HTTP_ORIGIN="http://evil.local")
        response_denied = cors.process_response(req_resp_denied, JsonResponse({}))
        self.assertNotIn("Access-Control-Allow-Origin", response_denied)

    def test_origin_filter_normalize_and_process_request(self):
        mw = OriginFilterMiddleware(get_response=lambda r: JsonResponse({}))
        self.assertEqual(mw._normalize(""), "")
        self.assertEqual(mw._normalize("front.local"), "http://front.local")
        self.assertEqual(mw._normalize("https://front.local/"), "https://front.local")

        req_options = self.rf.options("/")
        self.assertIsNone(mw.process_request(req_options))

        req_allowed = self.rf.get("/", HTTP_ORIGIN="http://front.local")
        self.assertIsNone(mw.process_request(req_allowed))

        req_host_fallback = self.rf.get("/", HTTP_HOST="api.local")
        self.assertIsNone(mw.process_request(req_host_fallback))

        req_denied = self.rf.get("/", HTTP_ORIGIN="http://evil.local")
        denied_response = mw.process_request(req_denied)
        self.assertIsNotNone(denied_response)
        self.assertEqual(denied_response.status_code, 403)
