import io
import json
import logging
import inspect
import tempfile
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from audit.decorators import (
    audit_log,
    audit_log_auth,
    get_user_from_access_token,
    sanitize_body,
    sanitize_query_params,
    sanitize_request_detail,
)
from audit.admin import AuditLogAdmin
from audit import views as audit_views
from audit.models import (
    CATEGORY_AUTH,
    CATEGORY_FINANCIAL,
    RESULT_ERROR,
    RESULT_FAILURE,
    RESULT_SUCCESS,
    AuditLog,
    ReleaseScriptExecution,
)
from audit.release_scripts import SemanticVersion, get_pending_release_scripts, load_release_scripts


class AuditLogModelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="audit_user",
            email="audit@test.com",
            password="testpass123",
        )

    def test_create_audit_log_with_user(self):
        log = AuditLog.objects.create(
            action="login",
            category=CATEGORY_AUTH,
            result=RESULT_SUCCESS,
            user=self.user,
            username=self.user.username,
            ip_address="127.0.0.1",
            path="/auth/token/",
            method="POST",
        )
        self.assertEqual(log.action, "login")
        self.assertEqual(log.username, "audit_user")
        self.assertEqual(log.user, self.user)

    def test_create_audit_log_without_user(self):
        log = AuditLog.objects.create(
            action="login",
            category=CATEGORY_AUTH,
            result=RESULT_FAILURE,
            username="unknown",
            ip_address="10.0.0.1",
            path="/auth/token/",
            method="POST",
        )
        self.assertIsNone(log.user)
        self.assertEqual(log.username, "unknown")

    def test_ordering_is_newest_first(self):
        AuditLog.objects.create(action="first", category=CATEGORY_AUTH, result=RESULT_SUCCESS)
        AuditLog.objects.create(action="second", category=CATEGORY_AUTH, result=RESULT_SUCCESS)
        logs = AuditLog.objects.all()
        self.assertEqual(logs[0].action, "second")
        self.assertEqual(logs[1].action, "first")

    def test_json_field_stores_data(self):
        detail = {"key": "value", "nested": {"a": 1}}
        log = AuditLog.objects.create(
            action="test",
            category=CATEGORY_AUTH,
            result=RESULT_SUCCESS,
            detail=detail,
        )
        log.refresh_from_db()
        self.assertEqual(log.detail["key"], "value")
        self.assertEqual(log.detail["nested"]["a"], 1)

    def test_user_deletion_preserves_log(self):
        temp_user = User.objects.create_user(username="temp", password="pass123")
        log = AuditLog.objects.create(
            action="login",
            category=CATEGORY_AUTH,
            result=RESULT_SUCCESS,
            user=temp_user,
            username="temp",
        )
        log_id = log.id
        temp_user.delete()
        log.refresh_from_db()
        self.assertIsNone(log.user)
        self.assertEqual(log.username, "temp")
        self.assertEqual(log.id, log_id)

    def test_str_representation(self):
        log = AuditLog.objects.create(
            action="login",
            category=CATEGORY_AUTH,
            result=RESULT_SUCCESS,
            username="testuser",
        )
        self.assertIn("login", str(log))
        self.assertIn("testuser", str(log))
        self.assertIn("success", str(log))


class SanitizeBodyTestCase(TestCase):
    def test_sanitizes_password_fields(self):
        body = json.dumps({"username": "user", "password": "secret123"}).encode()
        result = sanitize_body(body)
        self.assertEqual(result["username"], "user")
        self.assertEqual(result["password"], "***")

    def test_sanitizes_multiple_sensitive_fields(self):
        body = json.dumps(
            {
                "token": "abc",
                "access_token": "xyz",
                "refresh_token": "123",
                "secret": "s",
                "new_password": "np",
                "safe_field": "ok",
            }
        ).encode()
        result = sanitize_body(body)
        self.assertEqual(result["token"], "***")
        self.assertEqual(result["access_token"], "***")
        self.assertEqual(result["refresh_token"], "***")
        self.assertEqual(result["secret"], "***")
        self.assertEqual(result["new_password"], "***")
        self.assertEqual(result["safe_field"], "ok")

    def test_empty_body_returns_empty_dict(self):
        self.assertEqual(sanitize_body(b""), {})
        self.assertEqual(sanitize_body(None), {})

    def test_invalid_json_returns_empty_dict(self):
        self.assertEqual(sanitize_body(b"not json"), {})

    def test_truncates_large_body(self):
        large = json.dumps({"data": "x" * 5000}).encode()
        result = sanitize_body(large, max_size=50)
        self.assertEqual(result, {})


class AuditLogAuthDecoratorTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_login",
            email="login@test.com",
            password="user123",
            first_name="Test",
            last_name="Login",
        )

    def test_login_success_creates_audit_log(self):
        self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_login", "password": "user123"},
        )
        log = AuditLog.objects.filter(action="login").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.result, RESULT_SUCCESS)
        self.assertEqual(log.username, "test_login")
        self.assertEqual(log.category, CATEGORY_AUTH)
        self.assertEqual(log.method, "POST")
        self.assertIsNotNone(log.response_status)

    def test_login_failure_creates_audit_log(self):
        self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_login", "password": "wrong"},
        )
        log = AuditLog.objects.filter(action="login").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.result, RESULT_FAILURE)
        self.assertEqual(log.username, "test_login")

    @patch("authentication.views.send_verification_email_async")
    def test_signup_creates_audit_log(self, _mock_email):
        self.client.post(
            "/auth/signup",
            content_type="application/json",
            data={
                "username": "new_user",
                "password": "newpass123",
                "email": "new@test.com",
                "name": "New",
                "last_name": "User",
            },
        )
        log = AuditLog.objects.filter(action="signup").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.result, RESULT_SUCCESS)
        self.assertEqual(log.category, CATEGORY_AUTH)

    def test_sensitive_fields_sanitized_in_log(self):
        self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_login", "password": "user123"},
        )
        log = AuditLog.objects.filter(action="login").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.detail.get("password"), "***")
        self.assertEqual(log.detail.get("username"), "test_login")

    def test_ip_address_captured(self):
        self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_login", "password": "user123"},
            REMOTE_ADDR="192.168.1.100",
        )
        log = AuditLog.objects.filter(action="login").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.ip_address, "192.168.1.100")

    def test_logout_creates_audit_log(self):
        login_response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_login", "password": "user123"},
        )
        self.client.cookies = login_response.cookies
        self.client.get("/auth/signout")

        log = AuditLog.objects.filter(action="logout").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.result, RESULT_SUCCESS)
        self.assertEqual(log.username, "test_login")
        self.assertEqual(log.method, "GET")


class AuditLogDecoratorTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Suppress Django's error logging to avoid Python 3.14 + Django 4.2
        # template rendering incompatibility in log_response()
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="fin_user",
            email="fin@test.com",
            password="user123",
        )
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(self.user)

        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "fin_user", "password": "user123"},
        )
        self.cookies = response.cookies

    def _auth_post(self, path, data=None):
        self.client.cookies = self.cookies
        return self.client.post(
            path,
            content_type="application/json",
            data=data or {},
        )

    def test_tag_create_creates_audit_log(self):
        self._auth_post("/financial/tag/new", {"name": "Food", "color": "#FF0000"})
        log = AuditLog.objects.filter(action="tag.create").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.result, RESULT_SUCCESS)
        self.assertEqual(log.category, CATEGORY_FINANCIAL)
        self.assertEqual(log.target_model, "Tag")
        self.assertEqual(log.username, "fin_user")

    def test_tag_create_failure_creates_audit_log(self):
        self._auth_post("/financial/tag/new", {"name": "", "color": "#FF0000"})
        log = AuditLog.objects.filter(action="tag.create").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.result, RESULT_FAILURE)

    def test_unauthenticated_request_no_audit_log(self):
        self.client.cookies.clear()
        self.client.post(
            "/financial/tag/new/",
            content_type="application/json",
            data={"name": "Test", "color": "#000"},
        )
        log = AuditLog.objects.filter(action="tag.create").first()
        self.assertIsNone(log)


class AuditViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            password="admin123",
        )
        admin_group, _ = Group.objects.get_or_create(name="admin")
        admin_group.user_set.add(self.admin_user)

        self.regular_user = User.objects.create_user(
            username="regular_user",
            email="regular@test.com",
            password="user123",
        )
        user_group, _ = Group.objects.get_or_create(name="user")
        user_group.user_set.add(self.regular_user)

        AuditLog.objects.create(
            action="login",
            category=CATEGORY_AUTH,
            result=RESULT_SUCCESS,
            username="admin_user",
            ip_address="127.0.0.1",
            path="/auth/token/",
            method="POST",
        )
        AuditLog.objects.create(
            action="login",
            category=CATEGORY_AUTH,
            result=RESULT_FAILURE,
            username="unknown",
            ip_address="10.0.0.1",
            path="/auth/token/",
            method="POST",
        )
        AuditLog.objects.create(
            action="tag.create",
            category=CATEGORY_FINANCIAL,
            result=RESULT_SUCCESS,
            username="admin_user",
            path="/financial/tag/new/",
            method="POST",
        )

    def _login_as(self, username, password):
        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": username, "password": password},
        )
        self.client.cookies = response.cookies

    def test_get_audit_logs_as_admin(self):
        self._login_as("admin_user", "admin123")
        response = self.client.get("/audit/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("data", data)
        self.assertGreater(len(data["data"]), 0)

    def test_get_audit_logs_filtered_by_action(self):
        self._login_as("admin_user", "admin123")
        response = self.client.get("/audit/?action=login")
        data = response.json()["data"]
        for log in data["data"]:
            self.assertEqual(log["action"], "login")

    def test_get_audit_logs_filtered_by_category(self):
        self._login_as("admin_user", "admin123")
        response = self.client.get("/audit/?category=financial")
        data = response.json()["data"]
        for log in data["data"]:
            self.assertEqual(log["category"], "financial")

    def test_get_audit_logs_denied_for_non_admin(self):
        self._login_as("regular_user", "user123")
        response = self.client.get("/audit/")
        self.assertEqual(response.status_code, 403)

    def test_get_audit_stats_as_admin(self):
        self._login_as("admin_user", "admin123")
        response = self.client.get("/audit/stats/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("last_24h", data)
        self.assertIn("last_7d", data)
        self.assertIn("failed_logins_24h", data)

    def test_get_audit_stats_denied_for_non_admin(self):
        self._login_as("regular_user", "user123")
        response = self.client.get("/audit/stats/")
        self.assertEqual(response.status_code, 403)

    def test_get_audit_report_as_admin(self):
        self._login_as("admin_user", "admin123")
        response = self.client.get("/audit/report/")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("summary", data)
        self.assertIn("interactions_by_day", data)
        self.assertIn("by_action", data)
        self.assertIn("by_category", data)
        self.assertIn("by_user", data)
        self.assertIn("failures_by_action", data)
        self.assertEqual(data["summary"]["total_events"], 4)

    def test_get_audit_report_denied_for_non_admin(self):
        self._login_as("regular_user", "user123")
        response = self.client.get("/audit/report/")
        self.assertEqual(response.status_code, 403)

    def test_get_audit_report_filters(self):
        self._login_as("admin_user", "admin123")
        response = self.client.get("/audit/report/?action=login&category=auth")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["summary"]["total_events"], 3)
        self.assertEqual(data["filters"]["action"], "login")
        self.assertEqual(data["filters"]["category"], "auth")

    def test_pagination_works(self):
        self._login_as("admin_user", "admin123")
        response = self.client.get("/audit/?page_size=1&page=1")
        data = response.json()["data"]
        self.assertEqual(len(data["data"]), 1)
        self.assertTrue(data["has_next"])


class AuditDecoratorsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="audit-decorator", email="audit-decorator@test.com", password="123"
        )

    def setUp(self):
        self.rf = RequestFactory()

    def test_sanitize_helpers_cover_list_query_and_nondict_body(self):
        self.assertEqual(
            sanitize_body('{"password":"x","safe":"ok"}'),
            {"password": "***", "safe": "ok"},
        )
        self.assertEqual(sanitize_body('["a", {"token":"x"}]'), ["a", {"token": "***"}])
        self.assertEqual(sanitize_body('"text"'), "text")

        request = self.rf.get("/x", {"a": ["1", "2"], "token": "abc"})
        query = sanitize_query_params(request)
        self.assertEqual(query["a"], ["1", "2"])
        self.assertEqual(query["token"], "***")

        req_dict = self.rf.get("/x", {"q": "z"})
        req_dict._body = b'{"ok": true}'
        dict_detail = sanitize_request_detail(req_dict)
        self.assertEqual(dict_detail["ok"], True)
        self.assertEqual(dict_detail["query_params"]["q"], "z")

        req_non_dict = self.rf.get("/x", {"q": "x"})
        req_non_dict._body = b'["item"]'
        detail = sanitize_request_detail(req_non_dict)
        self.assertEqual(detail["body"], ["item"])
        self.assertEqual(detail["query_params"]["q"], "x")

    def test_sanitize_request_detail_handles_multipart_after_stream_read(self):
        uploaded_file = SimpleUploadedFile("bg.png", b"png", content_type="image/png")
        request = self.rf.post("/x?token=abc", {"icon_style": "P", "password": "secret", "background": uploaded_file})

        _ = request.POST
        detail = sanitize_request_detail(request)

        self.assertEqual(detail["icon_style"], "P")
        self.assertEqual(detail["password"], "***")
        self.assertEqual(detail["query_params"]["token"], "***")

    def test_get_user_from_access_token_missing_user_id_and_invalid_token(self):
        valid_token = str(AccessToken.for_user(self.user))
        request = self.rf.get("/x")
        request.COOKIES["access_token"] = valid_token

        with patch("audit.decorators.settings.ACCESS_TOKEN_NAME", "access_token"), patch(
            "audit.decorators.AccessToken.get", return_value=None
        ):
            self.assertIsNone(get_user_from_access_token(request))

        request_bad = self.rf.get("/x")
        request_bad.COOKIES["access_token"] = "invalid"
        with patch("audit.decorators.settings.ACCESS_TOKEN_NAME", "access_token"):
            self.assertIsNone(get_user_from_access_token(request_bad))

    def test_audit_log_and_audit_log_auth_error_branches(self):
        @audit_log("custom.action", CATEGORY_FINANCIAL, "X")
        def failing_view(request, *args, **kwargs):
            raise RuntimeError("boom")

        request = self.rf.post("/x", data='{"token":"s"}', content_type="application/json")
        with self.assertRaises(RuntimeError):
            failing_view(request, user=self.user, id=10)

        error_log = AuditLog.objects.filter(action="custom.action").first()
        self.assertIsNotNone(error_log)
        self.assertEqual(error_log.result, RESULT_ERROR)
        self.assertEqual(error_log.target_id, "10")

        @audit_log_auth("custom.auth")
        def failing_auth_view(request, *args, **kwargs):
            raise RuntimeError("boom-auth")

        request_auth = self.rf.post("/x", data='{"email":"audit-decorator@test.com"}', content_type="application/json")
        with self.assertRaises(RuntimeError):
            failing_auth_view(request_auth)

        auth_error_log = AuditLog.objects.filter(action="custom.auth").first()
        self.assertIsNotNone(auth_error_log)
        self.assertEqual(auth_error_log.result, RESULT_ERROR)
        self.assertEqual(auth_error_log.username, "audit-decorator")


class AuditViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="audit-view-admin", email="audit-view-admin@test.com", password="123"
        )
        now = timezone.now()
        AuditLog.objects.create(
            action="a1",
            category=CATEGORY_AUTH,
            result=RESULT_SUCCESS,
            user=cls.user,
            username=cls.user.username,
            ip_address="1.1.1.1",
            created_at=now,
        )
        AuditLog.objects.create(
            action="a2",
            category=CATEGORY_FINANCIAL,
            result=RESULT_FAILURE,
            user=cls.user,
            username=cls.user.username,
            ip_address="2.2.2.2",
            created_at=now,
        )

    def setUp(self):
        self.rf = RequestFactory()

    def test_get_audit_logs_all_filter_branches(self):
        request = self.rf.get(
            "/audit/",
            {
                "action": "a1",
                "category": CATEGORY_AUTH,
                "result": RESULT_SUCCESS,
                "user_id": self.user.id,
                "username": "audit-view",
                "ip_address": "1.1.1.1",
                "date_from": "2020-01-01",
                "date_to": "2030-01-01",
                "page": 1,
                "page_size": 5,
            },
        )
        response = inspect.unwrap(audit_views.get_audit_logs)(request, user=self.user)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["action"], "a1")

    def test_get_audit_report_filter_branches_and_limit_bounds(self):
        request_small_limit = self.rf.get(
            "/audit/report/",
            {
                "category": CATEGORY_AUTH,
                "action": "a1",
                "result": RESULT_SUCCESS,
                "user_id": self.user.id,
                "username": "audit-view",
                "date_from": "2020-01-01",
                "date_to": "2030-01-01",
                "limit": 0,
            },
        )
        response_small = inspect.unwrap(audit_views.get_audit_report)(request_small_limit, user=self.user)
        self.assertEqual(response_small.status_code, 200)
        data_small = json.loads(response_small.content)["data"]
        self.assertEqual(data_small["filters"]["action"], "a1")
        self.assertEqual(data_small["summary"]["total_events"], 1)

        request_big_limit = self.rf.get("/audit/report/", {"limit": 1000})
        response_big = inspect.unwrap(audit_views.get_audit_report)(request_big_limit, user=self.user)
        self.assertEqual(response_big.status_code, 200)


class AuditAdminRegressionTestCase(TestCase):
    def test_audit_admin_permissions_are_read_only(self):
        admin_instance = AuditLogAdmin(AuditLog, AdminSite())
        request = RequestFactory().get("/admin/")

        self.assertFalse(admin_instance.has_add_permission(request))
        self.assertFalse(admin_instance.has_change_permission(request))
        self.assertFalse(admin_instance.has_delete_permission(request))


class ReleaseScriptRegistryTestCase(TestCase):
    def test_semantic_version_parses_prefixed_and_unprefixed_values(self):
        self.assertEqual(str(SemanticVersion.parse("v2.1.3")), "2.1.3")
        self.assertEqual(str(SemanticVersion.parse("2.1.3")), "2.1.3")

    def test_load_release_scripts_sorts_by_version(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as registry:
            registry.write('<script version="2.0.0">ONEOFF_TEST_RELEASE_SCRIPT</script>\n')
            registry.write('<script version="1.9.9">ONEOFF_TEST_FAILING_SCRIPT</script>\n')

        scripts = load_release_scripts(registry.name)

        self.assertEqual(
            [script.command_name for script in scripts], ["ONEOFF_TEST_FAILING_SCRIPT", "ONEOFF_TEST_RELEASE_SCRIPT"]
        )

    def test_get_pending_release_scripts_skips_executed_and_operational_entries(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as registry:
            registry.write('<script version="2.0.1">ONEOFF_TEST_RELEASE_SCRIPT</script>\n')
            registry.write('<script version="2.0.1">cron_recalculate_invoices</script>\n')

        pending_scripts = get_pending_release_scripts(
            target_version="v2.0.1",
            executed_commands={("2.0.1", "ONEOFF_TEST_RELEASE_SCRIPT")},
            registry_path=registry.name,
        )

        self.assertEqual(pending_scripts, [])


class RunReleaseScriptsCommandTestCase(TestCase):
    def test_app_version_command_returns_current_version(self):
        from kawori.version import __version__

        out = io.StringIO()
        call_command("app_version", stdout=out)
        self.assertIn(__version__, out.getvalue())

    def test_run_release_scripts_executes_pending_registered_script(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as registry:
            registry.write('<script version="2.0.3">ONEOFF_TEST_RELEASE_SCRIPT</script>\n')

        with override_settings(RELEASE_SCRIPT_REGISTRY_PATH=registry.name):
            call_command("run_release_scripts", target_version="v2.0.3")

        execution = ReleaseScriptExecution.objects.get(script_name="ONEOFF_TEST_RELEASE_SCRIPT")
        self.assertEqual(execution.release_version, "2.0.3")
        self.assertEqual(execution.status, "success")

    def test_run_release_scripts_records_failure(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as registry:
            registry.write('<script version="2.0.3">ONEOFF_TEST_FAILING_SCRIPT</script>\n')

        with override_settings(RELEASE_SCRIPT_REGISTRY_PATH=registry.name):
            with self.assertRaisesMessage(Exception, "intentional failure"):
                call_command("run_release_scripts", target_version="v2.0.3")

        execution = ReleaseScriptExecution.objects.get(script_name="ONEOFF_TEST_FAILING_SCRIPT")
        self.assertEqual(execution.status, "failure")
