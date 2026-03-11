from __future__ import annotations

import argparse
import re
from pathlib import Path


def extract_release_notes(changelog_path: Path, version: str) -> str:
    normalized_version = version[1:] if version.startswith("v") else version
    content = changelog_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## v{re.escape(normalized_version)} - .*?(?=^## v|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if match:
        return match.group(0).strip() + "\n"

    return f"Release v{normalized_version}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a version section from the changelog.")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    notes = extract_release_notes(Path(args.changelog), args.version)
    Path(args.output).write_text(notes, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
