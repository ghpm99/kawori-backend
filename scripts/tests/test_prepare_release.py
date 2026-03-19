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

    def test_load_commits_ignores_release_and_sync_automation_commits(self) -> None:
        raw_log = (
            "aaa111\x1fbuild(release): prepare v1.6.0\x1f\x1e"
            "bbb222\x1fbuild(sync): merge main into develop\x1f\x1e"
            "ccc333\x1fchore(release): prepare v1.5.0\x1f\x1e"
            "ddd444\x1ffeat(payment): add Pix reconciliation endpoint\x1f\x1e"
        )

        with patch.object(prepare_release, "git", return_value=raw_log):
            commits = prepare_release.load_commits("origin/main", "HEAD")

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].sha, "ddd444")
        self.assertEqual(commits[0].subject, "feat(payment): add Pix reconciliation endpoint")


class LoadLatestTagVersionTests(TestCase):
    def test_load_latest_tag_version_uses_only_tags_merged_into_base_ref(self) -> None:
        with patch.object(prepare_release, "git", return_value="v1.4.0\nv1.5.0\nnot-a-version"):
            version = prepare_release.load_latest_tag_version("origin/main")

        self.assertEqual(str(version), "1.5.0")


class ComplianceHintsTests(TestCase):
    def test_build_compliance_hints_flags_missing_oneoff_registry(self) -> None:
        commits = [
            prepare_release.CommitInfo(
                sha="abc123",
                subject="feat(financial): change payment import flow",
                body="",
                type="feat",
                scope="financial",
                breaking=False,
            )
        ]
        changed_files = [
            "financial/migrations/0002_auto.py",
            "financial/management/commands/process_imported_payments.py",
        ]

        hints = prepare_release.build_compliance_hints(commits, changed_files)

        self.assertTrue(hints["inferred_oneoff_need"])
        self.assertFalse(hints["scripts_registry_touched"])
        self.assertFalse(hints["oneoff_registry_complete"])

    def test_build_pr_body_includes_compliance_and_test_sections(self) -> None:
        version = prepare_release.SemanticVersion.parse("1.8.0")
        commits = [
            prepare_release.CommitInfo(
                sha="def456",
                subject="fix(payment): keep fallback when ai is unavailable",
                body="",
                type="fix",
                scope="payment",
                breaking=False,
            )
        ]
        compliance_hints = {
            "inferred_oneoff_need": True,
            "scripts_registry_touched": True,
            "oneoff_registry_complete": False,
            "docs_touched": ["docs/engineering-rules.md"],
        }
        test_hints = ["python manage.py test payment"]

        body = prepare_release.build_pr_body(version, commits, compliance_hints, test_hints)

        self.assertIn("### Compliance Assistant", body)
        self.assertIn("### Regression Test Suggestions", body)
        self.assertIn("python manage.py test payment", body)
