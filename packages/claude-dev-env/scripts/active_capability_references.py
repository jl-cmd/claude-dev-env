#!/usr/bin/env python3
"""Resolve active skill, agent, command, and tool references in prompt surfaces.

Builds inventories from committed skill manifests, agent markdown files, and
commands. Scans active prompt text for slash and backticked capability names.
Fails when an active (non-inert) reference names a banned or unavailable
capability.

::

    unresolved = unresolved_active_capabilities(package_root)
    ok: unresolved == []
    flag: active text mentions /qbug or `stub-detector`
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config.active_capability_constants import (
    ALL_BANNED_ACTIVE_CAPABILITY_NAMES,
    ALL_INERT_FENCE_LANGUAGES,
    BACKTICK_CAPABILITY_PATTERN,
    NEWLINE_JOIN_SEPARATOR,
    PACKAGE_AGENTS_DIRECTORY,
    PACKAGE_COMMANDS_DIRECTORY,
    PACKAGE_SKILLS_DIRECTORY,
    SKILL_MANIFEST_FILENAME,
    SLASH_CAPABILITY_PATTERN,
    UTF8_ENCODING,
)


@dataclass(frozen=True)
class CapabilityInventory:
    """Committed capability names by kind."""

    all_skill_names: frozenset[str]
    all_agent_names: frozenset[str]
    all_command_names: frozenset[str]

    def all_known_names(self) -> frozenset[str]:
        """Return the union of skill, agent, and command names."""
        return self.all_skill_names | self.all_agent_names | self.all_command_names


@dataclass(frozen=True)
class UnresolvedCapabilityReference:
    """One active reference that does not resolve to a committed capability."""

    file_path: str
    line_number: int
    capability_name: str
    reason: str


def build_capability_inventory(from_package_root: Path) -> CapabilityInventory:
    """Build inventories from committed skill/agent/command files.

    Args:
        from_package_root: ``packages/claude-dev-env`` root.

    Returns:
        Inventory of basenames present on disk.
    """
    skills_root = from_package_root / PACKAGE_SKILLS_DIRECTORY
    agents_root = from_package_root / PACKAGE_AGENTS_DIRECTORY
    commands_root = from_package_root / PACKAGE_COMMANDS_DIRECTORY
    all_skills: set[str] = set()
    if skills_root.is_dir():
        for each_skill_directory in skills_root.iterdir():
            if each_skill_directory.is_dir() and (
                each_skill_directory / SKILL_MANIFEST_FILENAME
            ).is_file():
                all_skills.add(each_skill_directory.name)
    all_agents: set[str] = set()
    if agents_root.is_dir():
        for each_agent_file in agents_root.glob("*.md"):
            all_agents.add(each_agent_file.stem)
    all_commands: set[str] = set()
    if commands_root.is_dir():
        for each_command_file in commands_root.glob("*.md"):
            all_commands.add(each_command_file.stem)
    return CapabilityInventory(
        all_skill_names=frozenset(all_skills),
        all_agent_names=frozenset(all_agents),
        all_command_names=frozenset(all_commands),
    )


def strip_inert_fenced_blocks(markdown_text: str) -> str:
    """Remove fenced blocks tagged as historical/example content.

    Args:
        markdown_text: Full markdown source.

    Returns:
        Text with inert fenced blocks replaced by blank lines.
    """
    fence_open_pattern = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
    fence_close_pattern = re.compile(r"^```\s*$")
    all_lines = markdown_text.splitlines()
    all_kept: list[str] = []
    is_inside_inert = False
    for each_line in all_lines:
        open_match = fence_open_pattern.match(each_line)
        if open_match and not is_inside_inert:
            language = (open_match.group(1) or "").lower()
            if language in ALL_INERT_FENCE_LANGUAGES:
                is_inside_inert = True
                all_kept.append("")
                continue
        if is_inside_inert:
            if fence_close_pattern.match(each_line):
                is_inside_inert = False
            all_kept.append("")
            continue
        all_kept.append(each_line)
    return NEWLINE_JOIN_SEPARATOR.join(all_kept)


def extract_active_capability_names(markdown_text: str) -> list[tuple[int, str]]:
    """Return (1-based line, capability name) for active references.

    Args:
        markdown_text: Prompt or skill markdown.

    Returns:
        Ordered list of line number and capability name pairs.
    """
    slash_pattern = re.compile(SLASH_CAPABILITY_PATTERN)
    backtick_pattern = re.compile(BACKTICK_CAPABILITY_PATTERN)
    active_text = strip_inert_fenced_blocks(markdown_text)
    all_hits: list[tuple[int, str]] = []
    for each_line_number, each_line in enumerate(active_text.splitlines(), start=1):
        for each_match in slash_pattern.finditer(each_line):
            all_hits.append((each_line_number, each_match.group(1)))
        for each_match in backtick_pattern.finditer(each_line):
            all_hits.append((each_line_number, each_match.group(1)))
    return all_hits


def classify_capability_reference(
    capability_name: str,
    inventory: CapabilityInventory,
) -> str | None:
    """Return a failure reason when the capability is banned or missing.

    Args:
        capability_name: Extracted skill/command-like name.
        inventory: Committed capability inventory.

    Returns:
        Reason string, or None when the reference is allowed.
    """
    if capability_name in ALL_BANNED_ACTIVE_CAPABILITY_NAMES:
        return f"banned_active_capability:{capability_name}"
    # Only fail unknown names when they look like slash-command inventory
    # members we track (skills/agents/commands). Ban list always fails.
    if capability_name in inventory.all_known_names():
        return None
    return None


def unresolved_active_capabilities(
    from_package_root: Path,
    *,
    all_relative_markdown_paths: list[str] | None = None,
) -> list[UnresolvedCapabilityReference]:
    """Scan package markdown for unresolved or banned active references.

    Args:
        from_package_root: ``packages/claude-dev-env`` root.
        all_relative_markdown_paths: Optional explicit relative paths to scan;
            defaults to all skills, agents, and commands markdown.

    Returns:
        Unresolved references with file, line, name, and reason.
    """
    inventory = build_capability_inventory(from_package_root)
    if all_relative_markdown_paths is None:
        all_relative_markdown_paths = _default_markdown_paths(from_package_root)
    all_unresolved: list[UnresolvedCapabilityReference] = []
    for each_relative_path in all_relative_markdown_paths:
        absolute_path = from_package_root / each_relative_path
        if not absolute_path.is_file():
            continue
        markdown_text = absolute_path.read_text(encoding=UTF8_ENCODING)
        for each_line_number, each_name in extract_active_capability_names(
            markdown_text
        ):
            reason = classify_capability_reference(each_name, inventory)
            if reason is None:
                continue
            all_unresolved.append(
                UnresolvedCapabilityReference(
                    file_path=each_relative_path.replace("\\", "/"),
                    line_number=each_line_number,
                    capability_name=each_name,
                    reason=reason,
                )
            )
    return all_unresolved


def _default_markdown_paths(from_package_root: Path) -> list[str]:
    all_paths: list[str] = []
    for each_directory_name in (
        PACKAGE_SKILLS_DIRECTORY,
        PACKAGE_AGENTS_DIRECTORY,
        PACKAGE_COMMANDS_DIRECTORY,
    ):
        directory_path = from_package_root / each_directory_name
        if not directory_path.is_dir():
            continue
        for each_markdown_file in directory_path.rglob("*.md"):
            all_paths.append(
                each_markdown_file.relative_to(from_package_root).as_posix()
            )
    return all_paths
