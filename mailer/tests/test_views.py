import json

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from mailer.models import UserEmailPreference


class EmailPreferencesViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="prefviewuser", email="pref@test.com", password="testpass123")
        group = Group.objects.create(name="user")
        group.user_set.add(cls.user)

    def setUp(self):
        response = self.client.post(
            reverse("da_token_obtain_pair"),
            data={"username": "prefviewuser", "password": "testpass123"},
            content_type="application/json",
        )
        self.client.cookies = response.cookies

    def test_get_creates_default_preferences(self):
        self.assertFalse(UserEmailPreference.objects.filter(user=self.user).exists())
        response = self.client.get(reverse("email_preferences"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["allow_all_emails"])
        self.assertTrue(data["allow_notification"])
        self.assertTrue(data["allow_promotional"])
        self.assertTrue(UserEmailPreference.objects.filter(user=self.user).exists())

    def test_put_updates_preferences(self):
        response = self.client.put(
            reverse("email_preferences"),
            data=json.dumps({"allow_notification": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["allow_notification"])
        self.assertTrue(data["allow_all_emails"])
        pref = UserEmailPreference.objects.get(user=self.user)
        self.assertFalse(pref.allow_notification)

    def test_put_rejects_non_boolean(self):
        response = self.client.put(
            reverse("email_preferences"),
            data=json.dumps({"allow_all_emails": "yes"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_put_rejects_invalid_json(self):
        response = self.client.put(
            reverse("email_preferences"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_returns_401(self):
        self.client.cookies.clear()
        response = self.client.get(reverse("email_preferences"))
        self.assertEqual(response.status_code, 401)
