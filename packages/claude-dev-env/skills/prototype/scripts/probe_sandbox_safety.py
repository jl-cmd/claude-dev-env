#!/usr/bin/env python3
"""Prove both sandbox safety hooks block their probe payloads before trusting them.

::

    python probe_sandbox_safety.py --settings sandbox-settings.json
    exit 0  ->  pii_prevention_blocker and destructive_command_blocker both blocked
    exit 3  ->  one hook allowed its probe payload or errored

The probe reads each safety hook command from the settings, feeds it a
PreToolUse payload the hook's own tests prove it blocks, and confirms the
hook returns a deny-or-ask decision. It runs the hook scripts directly, so
it confirms each script is present, imports its constants package, and
blocks its probe payload — it does not exercise Claude Code's matcher
dispatch.
"""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import subprocess
import sys
from pathlib import Path

from build_sandbox_settings import read_settings_document
from prototype_scripts_constants.build_sandbox_settings_constants import (
    ALL_SAFETY_HOOK_SCRIPT_BASENAMES,
    COMMAND_KEY,
    HOOKS_KEY,
    MATCHER_KEY,
    PRE_TOOL_USE_KEY,
)
from prototype_scripts_constants.probe_sandbox_safety_constants import (
    ALL_BLOCK_DECISION_VALUES,
    ALL_DESTRUCTIVE_PROBE_COMMAND_TOKENS,
    COMMAND_TOKEN_JOIN_SEPARATOR,
    DESTRUCTIVE_PROBE_TOOL_NAME,
    ENVELOPE_HOOK_EVENT_NAME_KEY,
    ENVELOPE_HOOK_EVENT_NAME_VALUE,
    ENVELOPE_SESSION_ID_KEY,
    ENVELOPE_SESSION_ID_VALUE,
    ENVELOPE_TOOL_INPUT_KEY,
    ENVELOPE_TOOL_NAME_KEY,
    HOOK_OUTPUT_KEY,
    MATCHER_JOIN_SEPARATOR,
    PERMISSION_DECISION_KEY,
    PII_PROBE_CONTENT_TEMPLATE,
    PII_PROBE_FILE_PATH,
    PII_PROBE_TOKEN_BODY_CHARACTER,
    PII_PROBE_TOKEN_BODY_LENGTH,
    PII_PROBE_TOKEN_PREFIX,
    PII_PROBE_TOOL_NAME,
    PROBE_FAILURE_EXIT_CODE,
    PROBE_HOOK_TIMEOUT_SECONDS,
    PROBE_SUCCESS_EXIT_CODE,
    TOOL_INPUT_COMMAND_KEY,
    TOOL_INPUT_CONTENT_KEY,
    TOOL_INPUT_FILE_PATH_KEY,
)
from prototype_scripts_constants.prototype_common_constants import LOGGING_FORMAT

logger = logging.getLogger("probe_sandbox_safety")


def _build_pii_probe_payload() -> dict:
    synthetic_secret = (
        PII_PROBE_TOKEN_PREFIX
        + PII_PROBE_TOKEN_BODY_CHARACTER * PII_PROBE_TOKEN_BODY_LENGTH
    )
    probe_content = PII_PROBE_CONTENT_TEMPLATE.format(secret=synthetic_secret)
    return {
        ENVELOPE_SESSION_ID_KEY: ENVELOPE_SESSION_ID_VALUE,
        ENVELOPE_HOOK_EVENT_NAME_KEY: ENVELOPE_HOOK_EVENT_NAME_VALUE,
        ENVELOPE_TOOL_NAME_KEY: PII_PROBE_TOOL_NAME,
        ENVELOPE_TOOL_INPUT_KEY: {
            TOOL_INPUT_FILE_PATH_KEY: PII_PROBE_FILE_PATH,
            TOOL_INPUT_CONTENT_KEY: probe_content,
        },
    }


def _build_destructive_probe_payload() -> dict:
    destructive_command = COMMAND_TOKEN_JOIN_SEPARATOR.join(
        ALL_DESTRUCTIVE_PROBE_COMMAND_TOKENS
    )
    return {
        ENVELOPE_SESSION_ID_KEY: ENVELOPE_SESSION_ID_VALUE,
        ENVELOPE_HOOK_EVENT_NAME_KEY: ENVELOPE_HOOK_EVENT_NAME_VALUE,
        ENVELOPE_TOOL_NAME_KEY: DESTRUCTIVE_PROBE_TOOL_NAME,
        ENVELOPE_TOOL_INPUT_KEY: {TOOL_INPUT_COMMAND_KEY: destructive_command},
    }


def build_probe_payload_for_basename(basename: str) -> dict:
    """Build the PreToolUse probe payload a safety hook is proven to block.

    ::

        "pii_prevention_blocker.py"       -> Write payload carrying a secret
        "destructive_command_blocker.py"  -> Bash payload carrying rm -rf

    Args:
        basename: the safety hook script basename to build a payload for.

    Returns:
        The PreToolUse payload the named hook blocks.

    Raises:
        ValueError: when the basename names no known safety hook.
    """
    if basename == ALL_SAFETY_HOOK_SCRIPT_BASENAMES[0]:
        return _build_pii_probe_payload()
    if basename == ALL_SAFETY_HOOK_SCRIPT_BASENAMES[1]:
        return _build_destructive_probe_payload()
    raise ValueError(f"no probe payload for hook basename: {basename}")


def _command_in_block_for_basename(hook_block: dict, basename: str) -> str | None:
    for each_subhook in hook_block.get(HOOKS_KEY, []):
        command = each_subhook.get(COMMAND_KEY, "")
        if basename in command:
            return command
    return None


def find_hook_command_for_basename(
    settings_document: dict, basename: str
) -> str | None:
    """Find the first hook command in the settings that runs the named script.

    Args:
        settings_document: the minimal sandbox settings document.
        basename: the safety hook script basename to look for.

    Returns:
        The command string that runs the named script, or None when no
        hook command names it.
    """
    pre_tool_use_blocks = settings_document.get(HOOKS_KEY, {}).get(PRE_TOOL_USE_KEY, [])
    for each_block in pre_tool_use_blocks:
        command = _command_in_block_for_basename(each_block, basename)
        if command is not None:
            return command
    return None


def _find_matchers_for_basename(settings_document: dict, basename: str) -> list[str]:
    pre_tool_use_blocks = settings_document.get(HOOKS_KEY, {}).get(PRE_TOOL_USE_KEY, [])
    all_matchers = []
    for each_block in pre_tool_use_blocks:
        names_basename = any(
            basename in each_subhook.get(COMMAND_KEY, "")
            for each_subhook in each_block.get(HOOKS_KEY, [])
        )
        if names_basename:
            all_matchers.append(str(each_block.get(MATCHER_KEY)))
    return all_matchers


def parse_command_argv(command: str) -> list[str]:
    """Split a hook command string into an argument vector, quotes removed.

    ::

        '"py" "a b.py"'  ->  ["py", "a b.py"]

    Args:
        command: the hook command string from the settings.

    Returns:
        The argument vector with any surrounding quotes stripped.
    """
    all_tokens = shlex.split(command, posix=False)
    return [each_token.strip('"').strip("'") for each_token in all_tokens]


def hook_blocks_probe(all_command_tokens: list[str], probe_payload: dict) -> bool:
    """Run a hook against its probe payload and report whether it blocks.

    Args:
        all_command_tokens: the hook argument vector to run.
        probe_payload: the PreToolUse payload fed to the hook on stdin.

    Returns:
        True when the hook emits a deny-or-ask decision, False when it
        allows, emits no decision, or errors.
    """
    try:
        completed_process = subprocess.run(
            all_command_tokens,
            input=json.dumps(probe_payload),
            text=True,
            capture_output=True,
            timeout=PROBE_HOOK_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if not completed_process.stdout.strip():
        return False
    try:
        parsed_hook_reply = json.loads(completed_process.stdout)
    except json.JSONDecodeError:
        return False
    decision = parsed_hook_reply.get(HOOK_OUTPUT_KEY, {}).get(PERMISSION_DECISION_KEY)
    return decision in ALL_BLOCK_DECISION_VALUES


def probe_safety_hook(settings_document: dict, basename: str) -> bool:
    """Probe one safety hook from the settings and report whether it blocks.

    Args:
        settings_document: the minimal sandbox settings document.
        basename: the safety hook script basename to probe.

    Returns:
        True when the hook blocks its probe payload, False otherwise.
    """
    command = find_hook_command_for_basename(settings_document, basename)
    if command is None:
        logger.error("no hook command in settings runs %s", basename)
        return False
    all_matchers = _find_matchers_for_basename(settings_document, basename)
    logger.info("%s matchers: %s", basename, MATCHER_JOIN_SEPARATOR.join(all_matchers))
    all_command_tokens = parse_command_argv(command)
    probe_payload = build_probe_payload_for_basename(basename)
    return hook_blocks_probe(all_command_tokens, probe_payload)


def _parse_arguments(all_arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", required=True, help="the sandbox settings file")
    return parser.parse_args(all_arguments)


def main(all_arguments: list[str] | None = None) -> int:
    """Probe both safety hooks and report whether the sandbox is contained.

    Args:
        all_arguments: the command-line arguments, or None to read sys.argv.

    Returns:
        0 when both safety hooks block their probe payloads, 3 when either
        allows, errors, or the settings cannot be read.
    """
    logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
    arguments = _parse_arguments(all_arguments)
    settings_path = Path(arguments.settings).expanduser()
    try:
        settings_document = read_settings_document(settings_path)
    except (OSError, json.JSONDecodeError) as read_error:
        logger.error("cannot read settings %s: %s", settings_path, read_error)
        return PROBE_FAILURE_EXIT_CODE
    all_hook_block_outcomes = [
        probe_safety_hook(settings_document, each_basename)
        for each_basename in ALL_SAFETY_HOOK_SCRIPT_BASENAMES
    ]
    if all(all_hook_block_outcomes):
        return PROBE_SUCCESS_EXIT_CODE
    return PROBE_FAILURE_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
