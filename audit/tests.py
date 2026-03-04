import json
import logging

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase

from audit.decorators import sanitize_body
from audit.models import (
    CATEGORY_AUTH,
    CATEGORY_FINANCIAL,
    RESULT_ERROR,
    RESULT_FAILURE,
    RESULT_SUCCESS,
    AuditLog,
)


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
        body = json.dumps({
            "token": "abc",
            "access_token": "xyz",
            "refresh_token": "123",
            "secret": "s",
            "new_password": "np",
            "safe_field": "ok",
        }).encode()
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

    def test_signup_creates_audit_log(self):
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
