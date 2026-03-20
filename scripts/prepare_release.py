from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # nosec B404
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

VERSION_FILE = Path("kawori/version.py")
CHANGELOG_FILE = Path("CHANGELOG.md")
RELEASE_BRANCH = "release/develop-to-main"
ALLOWED_TYPES = {"feat", "fix", "refactor", "docs", "test", "build", "chore"}
PATCH_TYPES = {"fix", "refactor", "docs", "test", "build", "chore"}
AUTOMATION_COMMIT_PATTERN = re.compile(r"^(?:build|chore)\((?:release|sync)\): ")


@dataclass(frozen=True, order=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "SemanticVersion":
        normalized = value.strip()
        if normalized.startswith("v"):
            normalized = normalized[1:]

        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", normalized)
        if not match:
            raise ValueError(f"Invalid semantic version: {value}")

        return cls(*(int(part) for part in match.groups()))

    def bump(self, bump_type: str) -> "SemanticVersion":
        if bump_type == "major":
            return SemanticVersion(self.major + 1, 0, 0)
        if bump_type == "minor":
            return SemanticVersion(self.major, self.minor + 1, 0)
        return SemanticVersion(self.major, self.minor, self.patch + 1)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    subject: str
    body: str
    type: str
    scope: str | None
    breaking: bool


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()  # nosec


def write_github_output(**values: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return

    with open(output_path, "a", encoding="utf-8") as output_file:
        for key, value in values.items():
            output_file.write(f"{key}={value}\n")


def load_current_version(version_file: Path) -> SemanticVersion:
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError(f"Unable to find __version__ in {version_file}")
    return SemanticVersion.parse(match.group(1))


def load_latest_tag_version(base_ref: str) -> SemanticVersion | None:
    tags = git("tag", "--merged", base_ref, "--list").splitlines()
    versions: list[SemanticVersion] = []
    for tag in tags:
        try:
            versions.append(SemanticVersion.parse(tag))
        except ValueError:
            continue
    return max(versions) if versions else None


def parse_conventional_commit(
    subject: str, body: str
) -> tuple[str | None, str | None, bool]:
    match = re.match(
        r"(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<summary>.+)",
        subject,
    )
    breaking_from_body = "BREAKING CHANGE:" in body
    if not match:
        return None, None, breaking_from_body

    commit_type = match.group("type")
    if commit_type not in ALLOWED_TYPES:
        return (
            None,
            match.group("scope"),
            breaking_from_body or bool(match.group("breaking")),
        )

    return (
        commit_type,
        match.group("scope"),
        breaking_from_body or bool(match.group("breaking")),
    )


def is_automation_commit(subject: str) -> bool:
    return bool(AUTOMATION_COMMIT_PATTERN.match(subject))


def load_commits(base_ref: str, head_ref: str) -> list[CommitInfo]:
    raw_log = git(
        "log", f"{base_ref}..{head_ref}", "--pretty=format:%H%x1f%s%x1f%b%x1e"
    )
    commits: list[CommitInfo] = []

    for entry in raw_log.split("\x1e"):
        entry = entry.strip("\n\r\t ")
        if not entry:
            continue
        parts = entry.split("\x1f", 2)
        if len(parts) == 2:
            parts.append("")
        if len(parts) != 3:
            raise ValueError(f"Unexpected git log entry format: {entry!r}")
        sha, subject, body = [part.strip() for part in parts]
        if subject.startswith("Merge "):
            continue
        if is_automation_commit(subject):
            continue
        commit_type, scope, breaking = parse_conventional_commit(subject, body)
        if not commit_type and not breaking:
            continue
        commits.append(
            CommitInfo(
                sha=sha,
                subject=subject,
                body=body,
                type=commit_type or "chore",
                scope=scope,
                breaking=breaking,
            )
        )

    return list(reversed(commits))


def load_changed_files(base_ref: str, head_ref: str) -> list[str]:
    raw_diff = git("diff", "--name-only", f"{base_ref}..{head_ref}")
    return [line.strip() for line in raw_diff.splitlines() if line.strip()]


def build_compliance_hints(
    commits: list[CommitInfo], changed_files: list[str]
) -> dict[str, Any]:
    touched_files = set(changed_files)
    touched_docs = {
        "docs/engineering-rules.md": "engineering_rules",
        "docs/release-deploy-plan.md": "release_deploy_plan",
        "docs/oneoff-registry.md": "oneoff_registry",
    }
    docs_touched = [key for key, value in touched_docs.items() if key in touched_files]
    scripts_registry_touched = "scripts.xml" in touched_files

    has_migrations = any("/migrations/" in path for path in changed_files)
    has_oneoff_command_change = any(
        "management/commands/ONEOFF_" in path for path in changed_files
    )
    has_import_flow_change = any(
        path.startswith("payment/")
        or path.startswith("financial/management/commands/process_imported_payments")
        for path in changed_files
    )
    inferred_oneoff_need = (
        has_migrations or has_oneoff_command_change or has_import_flow_change
    )
    oneoff_registry_complete = (
        scripts_registry_touched and "docs/oneoff-registry.md" in touched_files
    )

    return {
        "changed_files": changed_files[:120],
        "releasable_commit_count": len(commits),
        "inferred_oneoff_need": inferred_oneoff_need,
        "scripts_registry_touched": scripts_registry_touched,
        "oneoff_registry_complete": oneoff_registry_complete,
        "docs_touched": docs_touched,
    }


def build_regression_test_hints(changed_files: list[str]) -> list[str]:
    hints: list[str] = []
    if any(path.startswith("payment/") for path in changed_files):
        hints.append("python manage.py test payment")
    if any(path.startswith("financial/") for path in changed_files):
        hints.append("python manage.py test financial")
    if any(path.startswith("audit/") for path in changed_files):
        hints.append("python manage.py test audit")
    if any(path.startswith("mailer/") for path in changed_files):
        hints.append("python manage.py test mailer")
    if any(path.startswith("scripts/") for path in changed_files):
        hints.append("python -m unittest scripts.tests.test_prepare_release")
    if not hints:
        hints.append("python manage.py test")
    return hints


def build_ai_release_assistance(
    commits: list[CommitInfo], compliance_hints: dict[str, Any]
) -> dict[str, Any] | None:
    ai_enabled = os.environ.get("AI_ASSIST_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    has_any_key = bool(os.environ.get("OPENAI_API_KEY")) or bool(
        os.environ.get("ANTHROPIC_API_KEY")
    )
    if not ai_enabled or not has_any_key:
        return None

    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kawori.settings.development")
        import django

        django.setup()

        from ai.assist import safe_execute_ai_task
        from ai.prompt_service import build_ai_request_from_prompt
    except Exception:
        return None

    payload = {
        "commits": [
            {
                "sha": commit.sha[:7],
                "subject": commit.subject,
                "breaking": commit.breaking,
            }
            for commit in commits
        ],
        "compliance_hints": compliance_hints,
    }

    try:
        built_request = build_ai_request_from_prompt(
            prompt_key="release.compliance.v1",
            payload=json.dumps(payload, ensure_ascii=False),
            feature_name="release_compliance",
        )
        response = safe_execute_ai_task(
            built_request.task_request,
            feature_name="release_compliance",
        )
    except Exception:
        return None

    if response is None or not isinstance(response.output, dict):
        return None

    output = response.output
    notes = output.get("release_compliance_notes")
    suggested_tests = output.get("suggested_regression_tests")

    return {
        "release_compliance_notes": [
            str(item).strip() for item in notes or [] if str(item).strip()
        ][:8],
        "oneoff_required": bool(output.get("oneoff_required")),
        "oneoff_reason": str(output.get("oneoff_reason", "")).strip(),
        "suggested_regression_tests": [
            str(item).strip() for item in suggested_tests or [] if str(item).strip()
        ][:10],
        "trace_id": response.trace_id,
        "provider": response.provider,
        "model": response.model,
        "prompt_key": built_request.prompt_resolution.key,
        "prompt_source": built_request.prompt_resolution.source,
        "prompt_version": built_request.prompt_resolution.version,
        "prompt_hash": built_request.prompt_resolution.content_hash,
    }


def determine_bump(commits: Iterable[CommitInfo]) -> str | None:
    bump = None
    for commit in commits:
        if commit.breaking:
            return "major"
        if commit.type == "feat":
            bump = "minor"
            continue
        if commit.type in PATCH_TYPES and bump is None:
            bump = "patch"
    return bump


def update_version_file(version_file: Path, version: SemanticVersion) -> None:
    version_file.write_text(f'__version__ = "{version}"\n', encoding="utf-8")


def build_changelog_section(version: SemanticVersion, commits: list[CommitInfo]) -> str:
    sections = {
        "Breaking Changes": [commit for commit in commits if commit.breaking],
        "Features": [
            commit
            for commit in commits
            if commit.type == "feat" and not commit.breaking
        ],
        "Fixes": [commit for commit in commits if commit.type == "fix"],
        "Maintenance": [
            commit
            for commit in commits
            if commit.type in {"refactor", "docs", "test", "build", "chore"}
        ],
    }

    lines = [f"## v{version} - {date.today().isoformat()}", ""]
    for title, entries in sections.items():
        if not entries:
            continue
        lines.append(f"### {title}")
        for commit in entries:
            lines.append(f"- {commit.subject} ({commit.sha[:7]})")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def update_changelog(
    changelog_file: Path, version: SemanticVersion, commits: list[CommitInfo]
) -> None:
    new_section = build_changelog_section(version, commits)
    if changelog_file.exists():
        existing = changelog_file.read_text(encoding="utf-8")
    else:
        existing = "# Changelog\n\n"

    pattern = re.compile(
        rf"^## v{re.escape(str(version))} - .*?(?=^## v|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    if pattern.search(existing):
        updated = pattern.sub(new_section.rstrip() + "\n\n", existing, count=1)
    else:
        first_entry = re.search(r"^## v", existing, flags=re.MULTILINE)
        if first_entry:
            updated = (
                existing[: first_entry.start()]
                + new_section
                + "\n"
                + existing[first_entry.start() :]
            )
        elif existing.endswith("\n"):
            updated = existing + new_section + "\n"
        else:
            updated = existing + "\n\n" + new_section + "\n"

    changelog_file.write_text(updated, encoding="utf-8")


def build_pr_body(
    version: SemanticVersion,
    commits: list[CommitInfo],
    compliance_hints: dict[str, Any],
    regression_test_hints: list[str],
    ai_release_assistance: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"## Release v{version}",
        "",
        "This PR was prepared automatically from `develop`.",
        "",
        "### Included commits",
    ]
    lines.extend(f"- `{commit.sha[:7]}` {commit.subject}" for commit in commits)
    lines.append("")
    lines.append("### Checklist")
    lines.append("- [ ] Review changelog and version bump")
    lines.append("- [ ] Confirm migrations and one-offs are complete")
    lines.append("- [ ] Merge to publish tag and release")
    lines.append("")

    lines.append("### Compliance Assistant")
    lines.append(
        f"- inferred_oneoff_need: `{compliance_hints.get('inferred_oneoff_need')}`"
    )
    lines.append(
        f"- scripts.xml updated: `{compliance_hints.get('scripts_registry_touched')}`"
    )
    lines.append(
        f"- one-off registry complete: `{compliance_hints.get('oneoff_registry_complete')}`"
    )
    docs_touched = compliance_hints.get("docs_touched") or []
    if docs_touched:
        lines.append(f"- workflow docs touched: `{', '.join(docs_touched)}`")
    else:
        lines.append("- workflow docs touched: `none`")
    lines.append("")

    lines.append("### Regression Test Suggestions")
    for hint in regression_test_hints:
        lines.append(f"- `{hint}`")
    lines.append("")

    if ai_release_assistance:
        lines.append("### AI Release Assistant")
        for note in ai_release_assistance.get("release_compliance_notes", []):
            lines.append(f"- {note}")
        lines.append(
            f"- AI one-off required: `{ai_release_assistance.get('oneoff_required')}`"
        )
        if ai_release_assistance.get("oneoff_reason"):
            lines.append(
                f"- AI one-off reason: {ai_release_assistance.get('oneoff_reason')}"
            )
        ai_test_hints = ai_release_assistance.get("suggested_regression_tests", [])
        if ai_test_hints:
            lines.append("- AI suggested tests:")
            lines.extend(f"  - `{item}`" for item in ai_test_hints)
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare release metadata and update version/changelog files."
    )
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--version-file", default=str(VERSION_FILE))
    parser.add_argument("--changelog-file", default=str(CHANGELOG_FILE))
    parser.add_argument("--pr-body-file", default=".release-pr-body.md")
    args = parser.parse_args()

    version_file = Path(args.version_file)
    changelog_file = Path(args.changelog_file)
    commits = load_commits(args.base_ref, args.head_ref)
    bump = determine_bump(commits)

    if not commits or bump is None:
        write_github_output(release_needed="false")
        print("No releasable commits found.")
        return 0

    current_version = load_current_version(version_file)
    latest_tag_version = load_latest_tag_version(args.base_ref)
    if latest_tag_version and latest_tag_version > current_version:
        current_version = latest_tag_version

    next_version = current_version.bump(bump)
    update_version_file(version_file, next_version)
    update_changelog(changelog_file, next_version, commits)

    changed_files = load_changed_files(args.base_ref, args.head_ref)
    compliance_hints = build_compliance_hints(commits, changed_files)
    regression_test_hints = build_regression_test_hints(changed_files)
    ai_release_assistance = build_ai_release_assistance(commits, compliance_hints)

    pr_body = build_pr_body(
        next_version,
        commits,
        compliance_hints,
        regression_test_hints,
        ai_release_assistance=ai_release_assistance,
    )
    Path(args.pr_body_file).write_text(pr_body, encoding="utf-8")

    write_github_output(
        release_needed="true",
        version=str(next_version),
        tag=f"v{next_version}",
        branch_name=RELEASE_BRANCH,
        pr_title=f"build(release): prepare v{next_version}",
        pr_body_file=args.pr_body_file,
    )
    print(f"Prepared release v{next_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
