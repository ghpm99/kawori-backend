import builtins
import importlib
import os
import runpy
from unittest.mock import patch

from django.test import SimpleTestCase


class MetaCoverageRegressionTestCase(SimpleTestCase):
    def test_manage_main_importerror_branch(self):
        manage = importlib.import_module("manage")
        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "django.core.management":
                raise ImportError("forced")
            return original_import(name, globals, locals, fromlist, level)

        self.assertIsNotNone(fake_import("os"))

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(ImportError):
                manage.main()

    def test_development_settings_importerror_local_settings_branch(self):
        original_import = builtins.__import__
        target_file = os.path.join(os.getcwd(), "kawori", "settings", "development.py")

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "kawori.settings.local_settings":
                raise ImportError("forced")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            result = runpy.run_path(target_file)

        self.assertTrue(result.get("DEBUG"))
