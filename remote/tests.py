import inspect
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from lib import pusher as pusher_lib
from remote.models import Config, Screenshot
from remote import views


class RemoteViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="remote-reg", email="remote-reg@test.com", password="123")

    def setUp(self):
        self.rf = RequestFactory()

    def _call(self, fn, method="get", data=None, files=None):
        request_factory_method = getattr(self.rf, method.lower())
        if method.lower() == "get":
            request = request_factory_method("/", data=data or {})
        else:
            if files:
                request = request_factory_method("/", data=data or {})
            else:
                payload = json.dumps(data or {})
                request = request_factory_method("/", data=payload, content_type="application/json")
        if files:
            request.FILES.update(files)
        return inspect.unwrap(fn)(request, user=self.user)

    def test_send_command_and_input_device_views(self):
        with patch("remote.views.pusher.send_command") as mocked_cmd:
            response = self._call(views.send_command_view, method="post", data={"cmd": "dir"})
        self.assertEqual(response.status_code, 200)
        mocked_cmd.assert_called_once_with("dir")

        with patch("remote.views.pusher.send_hotkey") as mocked_hotkey:
            self._call(views.hotkey_view, method="post", data={"hotkey": "ctrl+c"})
        mocked_hotkey.assert_called_once_with("ctrl+c")

        with patch("remote.views.pusher.send_key_press") as mocked_key:
            self._call(views.key_press_view, method="post", data={"keys": ["a", "b"]})
        mocked_key.assert_called_once_with(["a", "b"])

        with patch("remote.views.pusher.mouse_move") as mocked_move:
            self._call(views.mouse_move_view, method="post", data={"x": 10, "y": 20})
        mocked_move.assert_called_once_with(10, 20)

        with patch("remote.views.pusher.mouse_button") as mocked_button:
            self._call(views.mouse_button_view, method="post", data={"button": "left"})
        mocked_button.assert_called_once_with("left")

        with patch("remote.views.pusher.mouse_scroll") as mocked_scroll:
            self._call(views.mouse_scroll_view, method="post", data={"value": -1})
        mocked_scroll.assert_called_once_with(-1)

        with patch("remote.views.pusher.mouse_move_button") as mocked_move_button:
            self._call(views.mouse_move_and_button, method="post", data={"x": 5, "y": 7, "button": "right"})
        mocked_move_button.assert_called_once_with(5, 7, "right")

    def test_screen_size_and_keyboard_keys_views(self):
        Config.objects.create(type=Config.CONFIG_SCREEN, value=json.dumps({"width": 1920, "height": 1080}))

        screen_response = self._call(views.screen_size_view, method="get")
        self.assertEqual(screen_response.status_code, 200)
        screen_payload = json.loads(screen_response.content)
        self.assertEqual(screen_payload["width"], 1920)
        self.assertEqual(screen_payload["height"], 1080)

        keyboard_response = self._call(views.keyboard_keys, method="get")
        self.assertEqual(keyboard_response.status_code, 200)
        keyboard_payload = json.loads(keyboard_response.content)
        self.assertIn("enter", keyboard_payload["data"])
        self.assertIn("ctrl", keyboard_payload["data"])

    def test_save_screenshot_view_missing_and_success(self):
        missing = self._call(views.save_screenshot_view, method="post", data={})
        self.assertEqual(missing.status_code, 400)

        upload = SimpleUploadedFile("shot.png", b"binary-image-content", content_type="image/png")
        screenshot_obj = MagicMock()
        screenshot_obj.image.save = MagicMock()

        with patch("remote.views.Screenshot.objects.filter", return_value=MagicMock(first=lambda: screenshot_obj)), patch(
            "remote.views.os.path.exists", return_value=True
        ), patch("remote.views.os.remove") as mocked_remove, patch(
            "remote.views.pusher.notify_screenshot"
        ) as mocked_notify:
            success = self._call(views.save_screenshot_view, method="post", data={}, files={"image": upload})

        self.assertEqual(success.status_code, 200)
        self.assertTrue(screenshot_obj.image.save.called)
        self.assertTrue(mocked_remove.called)
        mocked_notify.assert_called_once()

    def test_save_screenshot_view_creates_new_screenshot_when_not_found(self):
        upload = SimpleUploadedFile("shot2.png", b"binary-image-content", content_type="image/png")
        query = MagicMock()
        query.first.return_value = None

        with patch("remote.views.Screenshot.objects.filter", return_value=query), patch(
            "remote.views.os.path.exists", return_value=False
        ), patch(
            "remote.views.pusher.notify_screenshot"
        ):
            response = self._call(views.save_screenshot_view, method="post", data={}, files={"image": upload})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Screenshot.objects.count(), 1)


class PusherLibRegressionTestCase(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_send_helpers_trigger_expected_channels(self):
        with patch("lib.pusher.pusher_client.trigger") as mocked_trigger:
            pusher_lib.send_command("dir")
            pusher_lib.send_hotkey("ctrl+c")
            pusher_lib.send_key_press(["a"])
            pusher_lib.mouse_move(1, 2)
            pusher_lib.mouse_button("left")
            pusher_lib.notify_screenshot()
            pusher_lib.mouse_scroll(10)
            pusher_lib.mouse_move_button(3, 4, "right")

        self.assertEqual(mocked_trigger.call_count, 8)

    def test_channel_occupied_and_vacated(self):
        with patch("lib.pusher.pusher_client.trigger") as mocked_trigger:
            pusher_lib.channel_occupied({"channel": "private-status"})
            pusher_lib.channel_occupied({"channel": "private-remote"})
            pusher_lib.channel_vacated({"channel": "private-status"})
            pusher_lib.channel_vacated({"channel": "private-remote"})

        self.assertEqual(mocked_trigger.call_count, 4)

    def test_client_event_create_and_update_screen_config(self):
        Config.objects.filter(type=Config.CONFIG_SCREEN).delete()

        pusher_lib.client_event({"event": "client-screen", "data": '{"w": 100}'})
        created = Config.objects.filter(type=Config.CONFIG_SCREEN).first()
        self.assertIsNotNone(created)
        self.assertEqual(created.value, '{"w": 100}')

        pusher_lib.client_event({"event": "client-screen", "data": '{"w": 200}'})
        created.refresh_from_db()
        self.assertEqual(created.value, '{"w": 200}')

    def test_webhook_and_auth(self):
        request = self.rf.post("/", data="{}", content_type="application/json")
        request.META["HTTP_X_PUSHER_KEY"] = "k"
        request.META["HTTP_X_PUSHER_SIGNATURE"] = "s"

        with patch("lib.pusher.pusher_client.validate_webhook", return_value=None):
            invalid = pusher_lib.webhook(request)
        self.assertEqual(invalid.status_code, 400)

        with patch("lib.pusher.pusher_client.validate_webhook", return_value={"events": []}):
            ok = pusher_lib.webhook(request)
        self.assertEqual(ok.status_code, 200)

        with patch("lib.pusher.channel_occupied") as mocked_occ, patch("lib.pusher.channel_vacated") as mocked_vac, patch(
            "lib.pusher.client_event"
        ) as mocked_client, patch(
            "lib.pusher.pusher_client.validate_webhook",
            return_value={
                "events": [
                    {"name": "channel_occupied", "channel": "private-status"},
                    {"name": "channel_vacated", "channel": "private-remote"},
                    {"name": "client_event", "event": "client-screen", "data": "{}"},
                ]
            },
        ):
            response = pusher_lib.webhook(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mocked_occ.called)
        self.assertTrue(mocked_vac.called)
        self.assertTrue(mocked_client.called)

        with patch("lib.pusher.pusher_client.authenticate", return_value={"auth": "x"}):
            auth_response = pusher_lib.auth(request, "private-demo", "1.2")
        self.assertEqual(auth_response.status_code, 200)
