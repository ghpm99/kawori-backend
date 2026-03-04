import inspect
import json

from django.contrib.auth.models import Group, User
from django.test import RequestFactory, TestCase

from user_profile import views


class UserProfileViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="profile-user",
            email="profile@test.com",
            password="123",
            first_name="Profile",
            last_name="User",
        )
        cls.group_user = Group.objects.create(name="user")
        cls.group_financial = Group.objects.create(name="financial")
        cls.user.groups.add(cls.group_user, cls.group_financial)

    def setUp(self):
        self.rf = RequestFactory()

    def test_user_view_returns_expected_payload(self):
        request = self.rf.get("/")
        response = inspect.unwrap(views.user_view)(request, user=self.user)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["id"], self.user.id)
        self.assertEqual(payload["name"], self.user.get_full_name())
        self.assertEqual(payload["username"], self.user.username)
        self.assertEqual(payload["email"], self.user.email)
        self.assertFalse(payload["is_staff"])
        self.assertTrue(payload["is_active"])

    def test_user_groups_returns_group_names(self):
        request = self.rf.get("/")
        response = inspect.unwrap(views.user_groups)(request, user=self.user)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(set(payload["data"]), {"user", "financial"})
