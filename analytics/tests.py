import inspect
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

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

        mock_qs = Mock()
        mock_qs.count.return_value = 7

        with patch("analytics.views.datetime") as mocked_datetime, patch(
            "analytics.views.User.objects.filter", return_value=mock_qs
        ) as mocked_filter:
            mocked_datetime.now.return_value = expected_date + timedelta(days=7)
            response = inspect.unwrap(views.get_new_users)(request, user=self.user)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload, {"new_users": 7})
        mocked_filter.assert_called_once_with(
            is_active=True, date_joined=expected_date
        )
