"""Unit tests for pr-description-enforcer PreToolUse hook entry flow."""

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
from blocking.pr_description_command_parser import extract_body_from_command

hook_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer",
    _HOOK_DIR / "pr_description_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
validate_pr_body = hook_module.validate_pr_body


@pytest.fixture(autouse=True)
def _isolate_readability_state(tmp_path_factory, monkeypatch):
    """Redirect the three readability state files to per-test temp paths for every test.

    The enabled file is written with enabled=False so the readability check stays
    off for the entry-flow tests, isolating them from readability scoring and the
    live state directory.
    """
    per_test_state_dir = tmp_path_factory.mktemp("readability_state")
    strike_path = per_test_state_dir / "strikes.json"
    override_path = per_test_state_dir / "overrides.json"
    enabled_path = per_test_state_dir / "enabled.json"
    enabled_path.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(readability_module, "READABILITY_STATE_FILE", strike_path)
    monkeypatch.setattr(readability_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", override_path)
    monkeypatch.setattr(readability_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)


VALID_BODY = (
    "Allow commas in branch names so PRs whose head branch was generated from "
    "a title or external identifier no longer fail validation before any git "
    "operation.\n\n"
    "Fixes #1300.\n\n"
    "## Changes\n\n"
    "- `src/github/operations/branch.ts`: add `,` to the whitelist regex\n"
    "- `test/branch.test.ts`: 3 new cases covering comma-bearing branch names\n\n"
    "## Test plan\n\n"
    "- `bun test test/branch.test.ts`\n"
    "- `bun run typecheck`\n"
)


def test_validate_blocks_literal_empty_body() -> None:
    """A literal `gh pr create --body ""` must NOT skip enforcement. Empty-body
    extraction returns "" (distinct from shell-var's None), so the validator
    runs and blocks via the substantive-prose check. Conflating the two
    previously allowed `--body ""` to bypass validation entirely."""
    violations = validate_pr_body("")
    assert violations, (
        "Empty PR body must produce at least one violation (typically substantive "
        f"prose); got an empty list, which would let `--body \"\"` bypass enforcement."
    )


def test_body_file_content_validated(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    body = extract_body_from_command(
        f'gh pr create --title "T" --body-file {body_file}'
    )
    assert body == "Too short."
    violations = validate_pr_body(body)
    assert violations


def test_main_does_not_block_when_dash_b_only_appears_in_word() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {"command": 'gh pr create --title "fix sub-branch handling"'},
    }
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    assert "deny" not in captured_stdout.getvalue()


def test_main_does_not_block_when_no_body_flag_present() -> None:
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {"command": 'gh pr create --title "My PR"'},
    }
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    assert "deny" not in captured_stdout.getvalue()


def test_main_allows_through_stdin_sentinel_body_file() -> None:
    """--body-file - must not be blocked (stdin body is unauditable)."""
    import io
    import json
    from unittest.mock import patch
    hook_input = {
        "tool_name": "Bash",
        "tool_input": {"command": 'gh pr create --title "T" --body-file -'},
    }
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    assert "deny" not in captured_stdout.getvalue()


def _build_main_hook_input(command: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _run_main_and_capture_decision(hook_input: dict[str, object]) -> str:
    captured_stdout = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(hook_input))):
        with patch("sys.stdout", captured_stdout):
            try:
                hook_module.main()
            except SystemExit:
                pass
    return captured_stdout.getvalue()


def test_main_blocks_gh_pr_edit_short_body_flag() -> None:
    """gh pr edit 123 -b "short" must be caught -- the short -b flag is a valid alias for --body."""
    command = 'gh pr edit 123 -b "Too short."'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output
    assert "substantive prose" in decision_output.lower()


def test_main_blocks_gh_pr_edit_body_file_short_flag(tmp_path) -> None:
    """gh pr edit 123 -F body.md must be caught -- -F is the short alias for --body-file."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr edit 123 -F {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output
    assert "substantive prose" in decision_output.lower()


def test_main_blocks_gh_pr_edit_body_file_long_flag(tmp_path) -> None:
    """gh pr edit 123 --body-file body.md must also be caught (was missing from is_pr_edit detection)."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr edit 123 --body-file {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


def test_main_blocks_gh_pr_create_body_file_short_flag(tmp_path) -> None:
    """gh pr create -F body.md must be caught -- -F is the short alias for --body-file."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr create --title "T" -F {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


def test_main_blocks_gh_pr_create_body_file_long_flag(tmp_path) -> None:
    """gh pr create --body-file body.md must be caught -- was missing from is_pr_create detection."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr create --title "T" --body-file {body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


def test_main_blocks_gh_pr_edit_short_body_equals_form() -> None:
    """gh pr edit 123 -b="short" must be caught -- the -b= equals form was bypassing
    the pre-filter and silently approving short bodies."""
    command = 'gh pr edit 123 -b="Too short."'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output
    assert "substantive prose" in decision_output.lower()


def test_main_blocks_gh_pr_edit_short_body_file_equals_form(tmp_path) -> None:
    """gh pr edit 123 -F=body.md must be caught -- the -F= equals form was bypassing the pre-filter."""
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    command = f'gh pr edit 123 -F={body_file}'
    decision_output = _run_main_and_capture_decision(_build_main_hook_input(command))
    assert "deny" in decision_output


def test_build_short_failing_body_helper_is_removed() -> None:
    """The unused test helper `_build_short_failing_body` had zero call sites and
    must not be re-introduced."""
    test_module = sys.modules[__name__]
    assert not hasattr(test_module, "_build_short_failing_body"), (
        "_build_short_failing_body was re-introduced; it has no callers in this test file."
    )
