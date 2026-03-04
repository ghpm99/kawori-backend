import inspect
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from pusher_webhook import views


class PusherWebhookViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="pusher-reg", email="pusher-reg@test.com", password="123")

    def setUp(self):
        self.rf = RequestFactory()

    def test_pusher_webhook_delegates_to_lib(self):
        request = self.rf.post("/", data="{}", content_type="application/json")

        with patch("pusher_webhook.views.pusher.webhook", return_value=HttpResponse("ok")) as mocked_webhook:
            response = inspect.unwrap(views.pusher_webhook)(request)

        self.assertEqual(response.status_code, 200)
        mocked_webhook.assert_called_once_with(request)

    def test_pusher_auth_parses_body_and_calls_lib_auth(self):
        body = "channel_name=private-demo&socket_id=123.456"
        request = self.rf.post("/", data=body, content_type="application/x-www-form-urlencoded")

        with patch("pusher_webhook.views.pusher.auth", return_value=HttpResponse("auth-ok")) as mocked_auth:
            response = inspect.unwrap(views.pusher_auth)(request, user=self.user)

        self.assertEqual(response.status_code, 200)
        mocked_auth.assert_called_once_with(request, "private-demo", "123.456")
