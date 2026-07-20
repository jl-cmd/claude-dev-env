"""Tests for the hand-typed pytest count detector in PR description bodies.

A PR body that hand-types a pytest pass count (`40 passed`) drifts as commits
land and tests are added, so the measured number belongs in pasted run output.
These tests pin the detector that flags the drift-prone shape, the regions it
treats as pasted rather than authored, and the create/edit-only gate that runs
it. Bodies reach the hook through `--body-file`, the form real traffic uses, so
the fence and heading rules run against real newlines.
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

from blocking import pr_description_readability as readability_module
from blocking.pr_description_body_audit import contains_hardcoded_test_count_claim
from hooks_constants.pr_description_enforcer_constants import HARDCODED_TEST_COUNT_MESSAGE

_hook_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer_hardcoded_count",
    _HOOK_DIR / "pr_description_enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook_module)

SUBSTANTIVE_OPENING = (
    "Adds the sandbox probe suite that exercises the probe sandbox safety "
    "guarantees end to end, so a regression in the isolation boundary fails "
    "loudly instead of leaking into the caller's tree. The suite covers the "
    "temp-root boundary, the cleanup path, and the refusal to follow a symlink "
    "out of the sandbox.\n\n"
    "## Verification\n\n"
)
DRIFT_PRONE_BODY = (
    SUBSTANTIVE_OPENING
    + "`python -m pytest packages/claude-dev-env/skills/prototype/scripts/` -> 40 passed\n"
)
PASTED_OUTPUT_BODY = (
    SUBSTANTIVE_OPENING
    + "```\n"
    + "$ python -m pytest packages/claude-dev-env/skills/prototype/scripts/\n"
    + "46 passed in 1.20s\n"
    + "```\n"
)
PROOF_COMMENT_BODY = (
    "## Proof of work\n\n"
    "Ran the probe suite and read the counts off the run.\n\n"
    "`python -m pytest packages/claude-dev-env/skills/prototype/scripts/` -> 46 passed\n"
)


@pytest.fixture(autouse=True)
def _isolate_hook_side_effects(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point the readability state files at temp paths and silence block logging.

    Keeps the readability scorer off so the entry-flow assertions isolate the
    hand-typed-count rule from readability strikes, and keeps a denial in these
    tests out of the real block log.
    """
    per_test_state_dir = tmp_path_factory.mktemp("count_readability_state")
    enabled_path = per_test_state_dir / "enabled.json"
    enabled_path.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(readability_module, "READABILITY_STATE_FILE", per_test_state_dir / "strikes.json")
    monkeypatch.setattr(
        readability_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", per_test_state_dir / "overrides.json"
    )
    monkeypatch.setattr(readability_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)
    monkeypatch.setattr(hook_module, "log_hook_block", lambda **each_argument: None)


def _run_hook_and_capture_denial_reason(command: str) -> str | None:
    """Run the hook against one Bash command and return its denial reason.

    Args:
        command: The Bash command string the PreToolUse payload carries.

    Returns:
        The permissionDecisionReason text when the hook denies; None when it
        allows the command.
    """
    hook_input = {"tool_name": "Bash", "tool_input": {"command": command}}
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    emitted_payload = captured_stdout.getvalue().strip()
    if not emitted_payload:
        return None
    decision = json.loads(emitted_payload)
    decision_text: str = decision["hookSpecificOutput"]["permissionDecisionReason"]
    return decision_text


def _body_file_command(gh_invocation: str, body: str, body_directory: pathlib.Path) -> str:
    """Write the body to a file and return the gh command that reads it."""
    body_path = body_directory / "body.md"
    body_path.write_text(body, encoding="utf-8")
    return f'{gh_invocation} --body-file "{body_path}"'


def should_flag_a_hand_typed_count_beside_a_pytest_command() -> None:
    assert contains_hardcoded_test_count_claim(DRIFT_PRONE_BODY) is True


def should_flag_a_hand_typed_failure_count() -> None:
    body = "Adds the retry guard.\n\nAfter pytest ran the suite, 2 failed and both are fixed here.\n"
    assert contains_hardcoded_test_count_claim(body) is True


def should_flag_a_hand_typed_count_written_into_a_heading() -> None:
    body = "Adds the probe suite and runs it under pytest.\n\n## Suite: 40 passed\n\nProse body here.\n"
    assert contains_hardcoded_test_count_claim(body) is True


def should_ignore_a_pytest_command_carrying_no_count() -> None:
    body = (
        "Adds the sandbox probe suite.\n\n"
        "## Verification\n\n"
        "`python -m pytest packages/claude-dev-env/skills/prototype/scripts/`\n"
    )
    assert contains_hardcoded_test_count_claim(body) is False


@pytest.mark.parametrize(
    ("case_name", "body"),
    [
        (
            "backtick fence",
            "Adds the suite.\n\n```\n$ python -m pytest tests/\n46 passed in 1.20s\n```\n",
        ),
        (
            "tilde fence",
            "Adds the suite.\n\n~~~\n$ python -m pytest tests/\n46 passed in 1.20s\n~~~\n",
        ),
        (
            "blockquoted reviewer reply",
            "Adds the suite.\n\n> I ran python -m pytest tests/ and saw 46 passed.\n",
        ),
        (
            "results table row",
            "Adds the suite.\n\n| Command | Result |\n|---|---|\n| pytest tests/ | 46 passed |\n",
        ),
        (
            "count inside inline code",
            "Adds the suite.\n\nRan `python -m pytest tests/` and it reports `46 passed` now.\n",
        ),
    ],
)
def should_exempt_a_count_outside_the_authors_own_prose(case_name: str, body: str) -> None:
    assert contains_hardcoded_test_count_claim(body) is False, case_name


@pytest.mark.parametrize(
    ("case_name", "body"),
    [
        (
            "no pytest reference anywhere",
            "Adds the batch importer.\n\nThe importer wrote 40 passed records into the ledger.\n",
        ),
        (
            "hyphenated compound after the count word",
            "Adds the gate.\n\nThe pytest gate now covers 12 passed-through cases.\n",
        ),
        (
            "count and count word on separate lines",
            "Adds the queue.\n\n- Retry ceiling raised to 3\n- failed writes go to the dead letter log\n\nCovered by pytest.\n",
        ),
        (
            "pull request number reference",
            "Adds the gate.\n\nPR #301 passed review last week and set this pytest pattern.\n",
        ),
        (
            "package name rather than a run",
            "Adds the importer and runs it under pytest-xdist.\n\nThe reconciliation wrote 40 passed records.\n",
        ),
        (
            "config filename rather than a run",
            "Updates pytest.ini testpaths.\n\nThe queue drained after 8 failed retries.\n",
        ),
        (
            "adjacency manufactured by removing inline code",
            "Ran `pytest -q`. Fixture 3 `helper` passed the value on.\n",
        ),
        (
            "pytest named only inside pasted output",
            "Adds retry.\n\nOf 120 uploads, 3 failed and retried clean.\n\n```\n$ python -m pytest tests/\n12 passed\n```\n",
        ),
    ],
)
def should_ignore_a_count_that_is_not_a_hand_typed_test_result(case_name: str, body: str) -> None:
    assert contains_hardcoded_test_count_claim(body) is False, case_name


def should_deny_gh_pr_create_carrying_a_hand_typed_count(tmp_path: pathlib.Path) -> None:
    command = _body_file_command('gh pr create --title "Add probe suite"', DRIFT_PRONE_BODY, tmp_path)
    denial_reason = _run_hook_and_capture_denial_reason(command)
    assert denial_reason is not None
    assert HARDCODED_TEST_COUNT_MESSAGE in denial_reason


def should_deny_gh_pr_edit_carrying_a_hand_typed_count(tmp_path: pathlib.Path) -> None:
    command = _body_file_command("gh pr edit 301", DRIFT_PRONE_BODY, tmp_path)
    denial_reason = _run_hook_and_capture_denial_reason(command)
    assert denial_reason is not None
    assert HARDCODED_TEST_COUNT_MESSAGE in denial_reason


def should_allow_gh_pr_create_whose_count_is_pasted_run_output(tmp_path: pathlib.Path) -> None:
    command = _body_file_command('gh pr create --title "Add probe suite"', PASTED_OUTPUT_BODY, tmp_path)
    denial_reason = _run_hook_and_capture_denial_reason(command)
    assert denial_reason is None


def should_leave_a_proof_comment_count_to_the_proof_audit(tmp_path: pathlib.Path) -> None:
    command = _body_file_command("gh pr comment 301", PROOF_COMMENT_BODY, tmp_path)
    denial_reason = _run_hook_and_capture_denial_reason(command)
    assert denial_reason is not None
    assert HARDCODED_TEST_COUNT_MESSAGE not in denial_reason


def should_judge_a_chained_command_by_the_invocation_owning_the_body(tmp_path: pathlib.Path) -> None:
    comment_invocation = _body_file_command("gh pr comment 301", PROOF_COMMENT_BODY, tmp_path)
    command = f'{comment_invocation}\ngh pr edit 301 --title "Add probe suite"'
    denial_reason = _run_hook_and_capture_denial_reason(command)
    assert denial_reason is not None
    assert HARDCODED_TEST_COUNT_MESSAGE not in denial_reason
