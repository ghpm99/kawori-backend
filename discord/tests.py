import inspect
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from discord.views import guild, user


class DiscordViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="discord-admin", email="discord-admin@test.com", password="123")

    def setUp(self):
        self.rf = RequestFactory()

    def _cursor_cm(self, rows):
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        cursor_cm = MagicMock()
        cursor_cm.__enter__.return_value = cursor
        return cursor_cm

    def _call(self, fn, data=None):
        request = self.rf.get("/", data=data or {})
        return inspect.unwrap(fn)(request, user=self.admin)

    def test_get_all_users(self):
        rows = [(1, False, "1234", "uid-1", "2026-01-01", "Alice")]
        with patch("discord.views.user.connection.cursor", return_value=self._cursor_cm(rows)):
            response = self._call(user.get_all_users, data={"page": 1})

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["data"][0]["id"], 1)
        self.assertEqual(payload["data"][0]["name"], "Alice")

    def test_get_all_guilds(self):
        rows = [(7, True, False, "gid-1", "owner-1", "2026-01-02", "Guild X")]
        with patch("discord.views.guild.connection.cursor", return_value=self._cursor_cm(rows)):
            response = self._call(guild.get_all_guilds, data={"page": 1})

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["data"][0]["id"], 7)
        self.assertEqual(payload["data"][0]["name"], "Guild X")

    def test_get_all_members(self):
        rows = [(9, False, "mid-1", "gid-1", "uid-1", "Nick")]
        with patch("discord.views.guild.connection.cursor", return_value=self._cursor_cm(rows)):
            response = self._call(guild.get_all_members, data={"page": 1})

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["data"][0]["id"], 9)
        self.assertEqual(payload["data"][0]["nick"], "Nick")

    def test_get_all_roles(self):
        rows = [(11, True)]
        with patch("discord.views.guild.connection.cursor", return_value=self._cursor_cm(rows)):
            response = self._call(guild.get_all_roles, data={"page": 1})

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["data"][0]["id"], 11)
        self.assertTrue(payload["data"][0]["active"])
