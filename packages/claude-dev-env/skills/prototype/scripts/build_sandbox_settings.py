#!/usr/bin/env python3
"""Emit a minimal ``--settings`` file carrying only the two sandbox safety hooks.

::

    python build_sandbox_settings.py --out sandbox-settings.json
    sandbox-settings.json -> {"hooks": {"PreToolUse": [
        {"matcher": "Bash",      "hooks": [pii_prevention, destructive_command]},
        {"matcher": "Edit",      "hooks": [pii_prevention]},
        {"matcher": "MultiEdit", "hooks": [pii_prevention]},
        {"matcher": "Write",     "hooks": [pii_prevention]}]}}

The builder resolves each safety hook's command entry from the live settings
source, which carries the per-machine interpreter, absolute script path, and
timeout. It then registers each entry on the matchers the sandbox requires.
The personal-data gate covers every write surface and the command line. The
destructive-command gate covers the command line. When either safety hook is
absent from the source, the builder exits without writing, because a sandbox
cannot be contained without both.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from prototype_scripts_constants.config.build_sandbox_settings_constants import (
    ALL_REQUIRED_MATCHERS_BY_SAFETY_BASENAME,
    ALL_SAFETY_HOOK_SCRIPT_BASENAMES,
    BUILD_SUCCESS_EXIT_CODE,
    COMMAND_KEY,
    DEFAULT_SETTINGS_SOURCE,
    HOOKS_KEY,
    JSON_INDENT_SPACES,
    MATCHER_KEY,
    MISSING_BASENAMES_JOIN_SEPARATOR,
    PRE_TOOL_USE_KEY,
    SETTINGS_MISSING_SAFETY_HOOK_EXIT_CODE,
    SETTINGS_SOURCE_UNREADABLE_EXIT_CODE,
)
from prototype_scripts_constants.config.prototype_common_constants import (
    LOGGING_FORMAT,
    TEXT_ENCODING_UTF8,
)

logger = logging.getLogger("build_sandbox_settings")


def read_settings_document(source_path: Path) -> dict:
    """Load the live settings JSON the sandbox settings are resolved from.

    ::

        ~/.claude/settings.json  ->  parsed dict with hooks.PreToolUse blocks
    """
    return json.loads(source_path.read_text(encoding=TEXT_ENCODING_UTF8))


def _first_subhook_running(
    pre_tool_use_block: dict, script_basename: str
) -> dict | None:
    """Return the block's first sub-hook whose command runs the named script."""
    for each_subhook in pre_tool_use_block.get(HOOKS_KEY, []):
        if script_basename in each_subhook.get(COMMAND_KEY, ""):
            return each_subhook
    return None


def _first_block_running(
    all_pre_tool_use_blocks: list[dict], script_basename: str
) -> dict | None:
    """Return the first block's sub-hook entry that runs the named safety script."""
    for each_block in all_pre_tool_use_blocks:
        resolved_entry = _first_subhook_running(each_block, script_basename)
        if resolved_entry is not None:
            return resolved_entry
    return None


def resolve_safety_hook_entries(settings_document: dict) -> dict[str, dict]:
    """Resolve each safety hook's live sub-hook entry, keyed by script basename.

    ::

        live PreToolUse blocks
            -> {"pii_prevention_blocker.py": {type, command, timeout},
                "destructive_command_blocker.py": {type, command, timeout}}

    The captured entry carries the per-machine interpreter, absolute script
    path, and timeout, so the sandbox settings stay correct on any machine.

    Args:
        settings_document: the live settings JSON with hooks.PreToolUse blocks.

    Returns:
        The first matching sub-hook entry per safety basename; a basename with
        no matching sub-hook is absent from the mapping.
    """
    pre_tool_use_blocks = settings_document.get(HOOKS_KEY, {}).get(PRE_TOOL_USE_KEY, [])
    entry_by_basename: dict[str, dict] = {}
    for each_basename in ALL_SAFETY_HOOK_SCRIPT_BASENAMES:
        resolved_entry = _first_block_running(pre_tool_use_blocks, each_basename)
        if resolved_entry is not None:
            entry_by_basename[each_basename] = resolved_entry
    return entry_by_basename


def find_unresolved_safety_hook_basenames(
    entry_by_basename: dict[str, dict],
) -> list[str]:
    """List the safety hook basenames the live source resolved no command for.

    ::

        both resolved            -> []
        destructive unresolved   -> ["destructive_command_blocker.py"]

    Args:
        entry_by_basename: the resolved sub-hook entry per safety basename.

    Returns:
        The safety hook basenames absent from the mapping, empty when both
        resolved.
    """
    return [
        each_basename
        for each_basename in ALL_SAFETY_HOOK_SCRIPT_BASENAMES
        if each_basename not in entry_by_basename
    ]


def _build_pre_tool_use_blocks(entry_by_basename: dict[str, dict]) -> list[dict]:
    """Build one PreToolUse block per required matcher, in sorted matcher order."""
    entries_by_matcher: dict[str, list[dict]] = {}
    for each_basename in ALL_REQUIRED_MATCHERS_BY_SAFETY_BASENAME:
        resolved_entry = entry_by_basename[each_basename]
        for each_matcher in ALL_REQUIRED_MATCHERS_BY_SAFETY_BASENAME[each_basename]:
            entries_by_matcher.setdefault(each_matcher, []).append(resolved_entry)
    return [
        {MATCHER_KEY: each_matcher, HOOKS_KEY: entries_by_matcher[each_matcher]}
        for each_matcher in sorted(entries_by_matcher)
    ]


def build_minimal_settings(entry_by_basename: dict[str, dict]) -> dict:
    """Assemble the minimal settings document from the resolved safety entries.

    ::

        resolved entries -> {"hooks": {"PreToolUse": [required-matcher blocks]}}

    Args:
        entry_by_basename: the resolved sub-hook entry per safety basename.

    Returns:
        The minimal settings document registering each safety entry on the
        matchers the sandbox requires.
    """
    return {
        HOOKS_KEY: {PRE_TOOL_USE_KEY: _build_pre_tool_use_blocks(entry_by_basename)}
    }


def write_minimal_settings(minimal_settings: dict, out_path: Path) -> None:
    """Write the minimal settings document to the output path as pretty JSON."""
    serialized_settings = json.dumps(minimal_settings, indent=JSON_INDENT_SPACES)
    out_path.write_text(serialized_settings + "\n", encoding=TEXT_ENCODING_UTF8)


def _parse_arguments(all_arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="where to write the settings")
    parser.add_argument(
        "--settings-source",
        default=DEFAULT_SETTINGS_SOURCE,
        help="the live settings JSON to resolve the safety hook commands from",
    )
    return parser.parse_args(all_arguments)


def _load_settings_or_none(source_path: Path) -> dict | None:
    """Read and parse the settings source, logging and returning None on failure."""
    try:
        return read_settings_document(source_path)
    except (OSError, json.JSONDecodeError) as read_error:
        logger.error("cannot read settings source %s: %s", source_path, read_error)
        return None


def main(all_arguments: list[str] | None = None) -> int:
    """Build the minimal safety settings and write them to the output path.

    Args:
        all_arguments: the command-line arguments, or None to read sys.argv.

    Returns:
        0 after writing the settings, 2 when the source is unreadable, and 2
        when either safety hook is unresolved from the source.
    """
    logging.basicConfig(format=LOGGING_FORMAT)
    arguments = _parse_arguments(all_arguments)
    source_path = Path(arguments.settings_source).expanduser()
    settings_document = _load_settings_or_none(source_path)
    if settings_document is None:
        return SETTINGS_SOURCE_UNREADABLE_EXIT_CODE
    entry_by_basename = resolve_safety_hook_entries(settings_document)
    all_unresolved_basenames = find_unresolved_safety_hook_basenames(entry_by_basename)
    if all_unresolved_basenames:
        logger.error(
            "safety hook missing from settings source: %s",
            MISSING_BASENAMES_JOIN_SEPARATOR.join(all_unresolved_basenames),
        )
        return SETTINGS_MISSING_SAFETY_HOOK_EXIT_CODE
    minimal_settings = build_minimal_settings(entry_by_basename)
    out_path = Path(arguments.out).expanduser()
    write_minimal_settings(minimal_settings, out_path)
    sys.stdout.write(str(out_path) + "\n")
    return BUILD_SUCCESS_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
