from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_release.py"
SPEC = importlib.util.spec_from_file_location("prepare_release", MODULE_PATH)
prepare_release = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = prepare_release
SPEC.loader.exec_module(prepare_release)


class LoadCommitsTests(TestCase):
    def test_load_commits_handles_empty_commit_body(self) -> None:
        raw_log = "abc123\x1ffix(payment): keep parser stable\x1f\x1e"

        with patch.object(prepare_release, "git", return_value=raw_log):
            commits = prepare_release.load_commits("origin/main", "HEAD")

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].sha, "abc123")
        self.assertEqual(commits[0].subject, "fix(payment): keep parser stable")
        self.assertEqual(commits[0].body, "")
