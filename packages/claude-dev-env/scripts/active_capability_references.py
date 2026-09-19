#!/usr/bin/env python3
"""Resolve active skill, agent, command, and tool references in prompt surfaces.

Builds inventories from committed skill manifests, agent markdown files, and
commands. Scans active prompt text for slash and backticked capability names.
Fails when an active (non-inert) reference names a capability this package
shipped once and ships no longer, resolved from the ever-shipped registry
against what the tree holds today.

::

    unresolved = unresolved_active_capabilities(package_root)
    ok: unresolved == []
    flag: active text mentions a name the tree dropped
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from dev_env_scripts_constants.active_capability_constants import (
    ALL_INERT_FENCE_LANGUAGES,
    ALL_QUALIFIED_CAPABILITY_PATTERNS,
    ALL_UNREGISTERED_RETIRED_CAPABILITY_NAMES,
    BLANKED_SPAN,
    EVER_SHIPPED_NAME_PATTERN,
    EVER_SHIPPED_REGISTRY_RELATIVE_PATH,
    FENCE_CLOSE_PATTERN,
    FENCE_OPEN_PATTERN,
    NEWLINE_JOIN_SEPARATOR,
    PACKAGE_AGENTS_DIRECTORY,
    PACKAGE_COMMANDS_DIRECTORY,
    PACKAGE_ROOT_AGENTS_DIRECTORY,
    PACKAGE_ROOT_SKILLS_DIRECTORY,
    PACKAGE_SKILLS_DIRECTORY,
    RETIRED_REASON_PREFIX,
    SKILL_MANIFEST_FILENAME,
    MULTI_SEGMENT_PATH_PATTERN,
    SLASH_CAPABILITY_PATTERN,
    URL_PATTERN,
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
    """One active reference that names a capability the tree no longer holds."""

    file_path: str
    line_number: int
    capability_name: str
    reason: str


def _resolve_package_tree(
    from_package_root: Path,
    canonical_relative: str,
    package_root_name: str,
) -> Path:
    """Return the canonical tree when it exists, else the package-root name."""
    canonical_directory = from_package_root / canonical_relative
    if canonical_directory.is_dir():
        return canonical_directory
    return from_package_root / package_root_name


def build_capability_inventory(from_package_root: Path) -> CapabilityInventory:
    """Build inventories from committed skill/agent/command files.

    Args:
        from_package_root: ``packages/claude-dev-env`` root.

    Returns:
        Inventory of basenames present on disk.
    """
    skills_root = _resolve_package_tree(
        from_package_root,
        PACKAGE_SKILLS_DIRECTORY,
        PACKAGE_ROOT_SKILLS_DIRECTORY,
    )
    agents_root = _resolve_package_tree(
        from_package_root,
        PACKAGE_AGENTS_DIRECTORY,
        PACKAGE_ROOT_AGENTS_DIRECTORY,
    )
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
    fence_open_pattern = re.compile(FENCE_OPEN_PATTERN)
    fence_close_pattern = re.compile(FENCE_CLOSE_PATTERN)
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

    A slash reference counts as an invocation, and a qualified reference
    names a skill directory or manifest. A URL and a multi-segment path
    carry neither, so both are blanked before the scan.

    Args:
        markdown_text: Prompt or skill markdown.

    Returns:
        Ordered list of line number and capability name pairs.
    """
    slash_pattern = re.compile(SLASH_CAPABILITY_PATTERN)
    url_pattern = re.compile(URL_PATTERN)
    path_pattern = re.compile(MULTI_SEGMENT_PATH_PATTERN)
    all_qualified_patterns = [
        re.compile(each_pattern) for each_pattern in ALL_QUALIFIED_CAPABILITY_PATTERNS
    ]
    active_text = strip_inert_fenced_blocks(markdown_text)
    all_hits: list[tuple[int, str]] = []
    for each_line_number, each_line in enumerate(active_text.splitlines(), start=1):
        for each_pattern in all_qualified_patterns:
            for each_match in each_pattern.finditer(each_line):
                all_hits.append((each_line_number, each_match.group(1)))
        invocation_line = path_pattern.sub(
            BLANKED_SPAN, url_pattern.sub(BLANKED_SPAN, each_line)
        )
        for each_match in slash_pattern.finditer(invocation_line):
            all_hits.append((each_line_number, each_match.group(1)))
    return all_hits


def retired_capability_names(
    from_package_root: Path, inventory: CapabilityInventory
) -> frozenset[str]:
    """Return the capability names this package shipped once and ships no longer.

    The ever-shipped registry keeps every skill name the package released.
    Subtracting what the tree holds today leaves the retired set, so no hand
    kept list decides which name fails.

    Args:
        from_package_root: ``packages/claude-dev-env`` root.
        inventory: Names the tree holds today.

    Returns:
        Retired capability names.
    """
    registry_path = from_package_root / EVER_SHIPPED_REGISTRY_RELATIVE_PATH
    all_ever_shipped_names: set[str] = set(
        ALL_UNREGISTERED_RETIRED_CAPABILITY_NAMES
    )
    if registry_path.is_file():
        all_ever_shipped_names.update(
            re.findall(
                EVER_SHIPPED_NAME_PATTERN,
                registry_path.read_text(encoding=UTF8_ENCODING),
            )
        )
    return frozenset(all_ever_shipped_names - inventory.all_known_names())


def classify_capability_reference(
    capability_name: str, all_retired_names: frozenset[str]
) -> str | None:
    """Return a failure reason when the capability left the tree.

    Extractors also match ordinary prose tokens, so a name the package never
    shipped passes. A name it shipped once and ships no longer fails.

    Args:
        capability_name: Extracted skill/command-like name.
        all_retired_names: Names resolved by ``retired_capability_names``.

    Returns:
        Reason string, or None when the reference is allowed.
    """
    if capability_name in all_retired_names:
        return f"{RETIRED_REASON_PREFIX}{capability_name}"
    return None


def unresolved_active_capabilities(
    from_package_root: Path,
    *,
    all_relative_markdown_paths: list[str] | None = None,
) -> list[UnresolvedCapabilityReference]:
    """Scan package markdown for references to retired capabilities.

    Args:
        from_package_root: ``packages/claude-dev-env`` root.
        all_relative_markdown_paths: Optional explicit relative paths to scan;
            defaults to all skills, agents, and commands markdown.

    Returns:
        Retired references with file, line, name, and reason.
    """
    if all_relative_markdown_paths is None:
        all_relative_markdown_paths = _default_markdown_paths(from_package_root)
    all_retired_names = retired_capability_names(
        from_package_root, build_capability_inventory(from_package_root)
    )
    all_unresolved: list[UnresolvedCapabilityReference] = []
    for each_relative_path in all_relative_markdown_paths:
        absolute_path = from_package_root / each_relative_path
        if not absolute_path.is_file():
            continue
        markdown_text = absolute_path.read_text(encoding=UTF8_ENCODING)
        for each_line_number, each_name in extract_active_capability_names(
            markdown_text
        ):
            reason = classify_capability_reference(each_name, all_retired_names)
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
    directory_paths = [
        _resolve_package_tree(
            from_package_root,
            PACKAGE_SKILLS_DIRECTORY,
            PACKAGE_ROOT_SKILLS_DIRECTORY,
        ),
        _resolve_package_tree(
            from_package_root,
            PACKAGE_AGENTS_DIRECTORY,
            PACKAGE_ROOT_AGENTS_DIRECTORY,
        ),
        from_package_root / PACKAGE_COMMANDS_DIRECTORY,
    ]
    for directory_path in directory_paths:
        if not directory_path.is_dir():
            continue
        for each_markdown_file in directory_path.rglob("*.md"):
            all_paths.append(
                each_markdown_file.relative_to(from_package_root).as_posix()
            )
    return all_paths
