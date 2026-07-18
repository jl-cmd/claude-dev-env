"""Tests for the hand-typed pytest count detector in PR description bodies.

A PR description that hand-types a pytest pass count (`40 passed`) drifts as
commits land and tests are added; the count belongs in the proof comment as
pasted command output. These tests pin the detector that flags the drift-prone
prose shape while exempting pasted output inside code fences.
"""

import importlib.util
import io
import json
import pathlib
import sys
from unittest.mock import patch

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from blocking import pr_description_readability as readability_module
from blocking.pr_description_body_audit import contains_hardcoded_test_count_claim

_hook_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer_count",
    _HOOK_DIR / "pr_description_enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook_module)

DRIFT_PRONE_DESCRIPTION = (
    "Adds the sandbox probe suite that exercises the probe sandbox safety "
    "guarantees end to end.\n\n"
    "## Verification\n\n"
    "`python -m pytest packages/claude-dev-env/skills/prototype/scripts/` -> 40 passed\n"
)
HARDCODED_MESSAGE_FRAGMENT = "hand-types a pytest count"


@pytest.fixture(autouse=True)
def _isolate_readability_state(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect the three readability state files to per-test temp paths, disabled.

    Keeps the readability scorer off so the entry-flow assertions isolate the
    hand-typed-count rule from readability strikes and the live state directory.
    """
    per_test_state_dir = tmp_path_factory.mktemp("count_readability_state")
    enabled_path = per_test_state_dir / "enabled.json"
    enabled_path.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(readability_module, "READABILITY_STATE_FILE", per_test_state_dir / "strikes.json")
    monkeypatch.setattr(readability_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", per_test_state_dir / "overrides.json")
    monkeypatch.setattr(readability_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)


def _run_main_and_capture_decision(command: str) -> str:
    hook_input = {"tool_name": "Bash", "tool_input": {"command": command}}
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    return captured_stdout.getvalue()


def test_flags_hand_typed_count_next_to_pytest_command() -> None:
    drift_prone_body = (
        "Adds the sandbox probe suite.\n\n"
        "## Verification\n\n"
        "`python -m pytest packages/claude-dev-env/skills/prototype/scripts/` -> 40 passed\n"
    )
    assert contains_hardcoded_test_count_claim(drift_prone_body) is True


def test_ignores_body_with_pytest_command_but_no_count() -> None:
    body_without_count = (
        "Adds the sandbox probe suite.\n\n"
        "## Verification\n\n"
        "`python -m pytest packages/claude-dev-env/skills/prototype/scripts/`\n"
    )
    assert contains_hardcoded_test_count_claim(body_without_count) is False


def test_ignores_count_without_any_pytest_reference() -> None:
    unrelated_count_body = (
        "Adds the batch importer.\n\n"
        "The importer wrote 40 rows and the reviewer approved every one.\n"
    )
    assert contains_hardcoded_test_count_claim(unrelated_count_body) is False


def test_exempts_count_pasted_inside_a_fenced_code_block() -> None:
    pasted_output_body = (
        "Adds the sandbox probe suite.\n\n"
        "## Verification\n\n"
        "```\n"
        "$ python -m pytest packages/claude-dev-env/skills/prototype/scripts/\n"
        "46 passed in 1.20s\n"
        "```\n"
    )
    assert contains_hardcoded_test_count_claim(pasted_output_body) is False


def test_main_blocks_gh_pr_create_description_with_hand_typed_count() -> None:
    command = f'gh pr create --title "Add probe suite" --body {json.dumps(DRIFT_PRONE_DESCRIPTION)}'
    decision_output = _run_main_and_capture_decision(command)
    assert "deny" in decision_output
    assert HARDCODED_MESSAGE_FRAGMENT in decision_output


def test_main_leaves_proof_comment_count_alone() -> None:
    command = f'gh pr comment 301 --body {json.dumps(DRIFT_PRONE_DESCRIPTION)}'
    decision_output = _run_main_and_capture_decision(command)
    assert HARDCODED_MESSAGE_FRAGMENT not in decision_output
