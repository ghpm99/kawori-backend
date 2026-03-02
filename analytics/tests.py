import inspect
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from analytics import views


class AnalyticsViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="analytics-user", password="123")

    def setUp(self):
        self.rf = RequestFactory()

    def test_get_new_users_uses_expected_date_filter(self):
        request = self.rf.get("/")
        expected_date = timezone.make_aware(datetime(2026, 1, 10, 0, 0, 0))

        with patch("analytics.views.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = expected_date + timedelta(days=7)
            response = inspect.unwrap(views.get_new_users)(request, user=self.user)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("new_users", payload)
