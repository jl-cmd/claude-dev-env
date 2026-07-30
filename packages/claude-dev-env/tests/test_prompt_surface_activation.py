"""Assert every documented prompt surface has an activation classification.

Builds an inventory from package.json files, hooks.json registrations, and
on-disk installer roots. Surfaces that exist only as source but are claimed
as packaged fail. Every hook command path must resolve to a committed file.
"""

from __future__ import annotations

import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PACKAGE_ROOT.parent.parent

CLASS_PACKAGED = "packaged"
CLASS_SOURCE_ONLY = "source_only"
CLASS_CONTRADICTORY = "contradictory"

INSTALLER_SURFACE_DIRS: tuple[str, ...] = (
    "rules",
    "docs",
    "commands",
    "agents",
    "skills",
    "hooks",
    "system-prompts",
    "scripts",
    "_shared",
    "audit-rubrics",
    "output-styles",
)


def _load_package_files() -> set[str]:
    package_json = PACKAGE_ROOT / "package.json"
    payload = json.loads(package_json.read_text(encoding="utf-8"))
    return {
        each.rstrip("/")
        for each in payload.get("files", [])
        if isinstance(each, str) and not each.startswith("!")
    }


def _load_hook_commands() -> list[str]:
    hooks_json = PACKAGE_ROOT / "hooks" / "hooks.json"
    payload = json.loads(hooks_json.read_text(encoding="utf-8"))
    commands: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            command = node.get("command")
            if isinstance(command, str) and command.strip():
                commands.append(command)
            for each_value in node.values():
                walk(each_value)
        elif isinstance(node, list):
            for each_item in node:
                walk(each_item)

    walk(payload)
    return commands


def classify_surface(directory_name: str, packaged_names: set[str]) -> str:
    """Classify one top-level surface directory.

    Args:
        directory_name: Top-level package directory name.
        packaged_names: Basename entries from package.json files without slash.

    Returns:
        One of packaged, source_only, or contradictory.
    """
    on_disk = (PACKAGE_ROOT / directory_name).is_dir()
    is_packaged = directory_name in packaged_names
    if on_disk and is_packaged:
        return CLASS_PACKAGED
    if on_disk and not is_packaged:
        return CLASS_SOURCE_ONLY
    if not on_disk and is_packaged:
        return CLASS_CONTRADICTORY
    return CLASS_SOURCE_ONLY


def test_output_styles_is_packaged_not_source_only() -> None:
    packaged = _load_package_files()
    classification = classify_surface("output-styles", packaged)
    assert classification == CLASS_PACKAGED, (
        "output-styles must be packaged once documented as an installed surface; "
        f"got {classification}"
    )


def test_every_installer_surface_has_classification() -> None:
    packaged = _load_package_files()
    classifications = {
        each_name: classify_surface(each_name, packaged)
        for each_name in INSTALLER_SURFACE_DIRS
        if (PACKAGE_ROOT / each_name).exists() or each_name in packaged
    }
    assert classifications
    assert CLASS_CONTRADICTORY not in classifications.values(), classifications
    for each_name, each_class in classifications.items():
        assert each_class in {
            CLASS_PACKAGED,
            CLASS_SOURCE_ONLY,
        }, f"{each_name}={each_class}"


def test_hook_commands_resolve_to_committed_files() -> None:
    all_commands = _load_hook_commands()
    assert all_commands
    unresolved: list[str] = []
    for each_command in all_commands:
        # Hooks store absolute or relative python script paths after install rewrite;
        # in source, command often ends with a .py path segment.
        if ".py" not in each_command:
            continue
        script_token = each_command
        for each_part in each_command.replace("\\", "/").split():
            if each_part.endswith(".py"):
                script_token = each_part
                break
        relative = script_token.replace("\\", "/")
        if "packages/claude-dev-env/" in relative:
            relative = relative.split("packages/claude-dev-env/", 1)[1]
        elif relative.startswith("hooks/"):
            pass
        candidate = PACKAGE_ROOT / relative
        if not candidate.is_file():
            # try basename search under hooks/
            basename = Path(relative).name
            matches = list((PACKAGE_ROOT / "hooks").rglob(basename))
            if not matches:
                unresolved.append(each_command)
    assert not unresolved, "Unresolved hook commands:\n" + "\n".join(unresolved)
