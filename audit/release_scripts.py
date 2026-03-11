from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from django.conf import settings


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

        parts = normalized.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError(f"Invalid semantic version: {value}")

        return cls(*(int(part) for part in parts))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class ReleaseScript:
    version: SemanticVersion
    command_name: str

    @property
    def is_oneoff(self) -> bool:
        return self.command_name.startswith("ONEOFF_")


def _wrap_registry(raw_registry: str) -> str:
    return f"<scripts>\n{raw_registry}\n</scripts>"


def get_registry_path() -> Path:
    return Path(settings.RELEASE_SCRIPT_REGISTRY_PATH)


def load_release_scripts(registry_path: Path | None = None) -> list[ReleaseScript]:
    path = Path(registry_path or get_registry_path())
    if not path.exists():
        return []

    raw_content = path.read_text(encoding="utf-8").strip()
    if not raw_content:
        return []

    try:
        root = ElementTree.fromstring(_wrap_registry(raw_content))
    except ElementTree.ParseError as exc:
        raise ValueError(f"Invalid release script registry: {path}") from exc

    scripts: list[ReleaseScript] = []
    for node in root.findall("script"):
        version = node.attrib.get("version", "").strip()
        command_name = (node.text or "").strip()
        if not version or not command_name:
            continue

        scripts.append(
            ReleaseScript(
                version=SemanticVersion.parse(version),
                command_name=command_name,
            )
        )

    return sorted(scripts, key=lambda item: (item.version, item.command_name))


def get_pending_release_scripts(
    target_version: str,
    executed_commands: set[tuple[str, str]] | None = None,
    registry_path: Path | None = None,
    include_operational: bool = False,
) -> list[ReleaseScript]:
    normalized_target_version = SemanticVersion.parse(target_version)
    executed = executed_commands or set()

    pending_scripts = []
    for script in load_release_scripts(registry_path=registry_path):
        execution_key = (str(script.version), script.command_name)
        if script.version > normalized_target_version:
            continue
        if execution_key in executed:
            continue
        if not include_operational and not script.is_oneoff:
            continue
        pending_scripts.append(script)

    return pending_scripts
