"""Unit tests for pr-description-enforcer PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import sys
from unittest.mock import patch

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from _gh_body_arg_utils import get_logical_first_line

hook_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer",
    _HOOK_DIR / "pr-description-enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
extract_body_from_command = hook_module.extract_body_from_command
validate_pr_body = hook_module.validate_pr_body

VALID_BODY = (
    "## Description\n\nThis PR fixes a real bug.\n\n"
    "## Why\n\nBecause it was broken in production.\n\n"
    "## How\n\nRefactored the auth module to handle edge cases correctly.\n"
)


def test_extract_body_from_body_string() -> None:
    command = 'gh pr create --title "T" --body "Description and some text."'
    assert "Description" in extract_body_from_command(command)


def test_extract_body_from_body_file_space_form(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "T" --body-file {body_file}'
    assert extract_body_from_command(command) == VALID_BODY


def test_extract_body_from_body_file_equals_form(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "T" --body-file="{body_file}"'
    assert extract_body_from_command(command) == VALID_BODY


def test_extract_body_from_body_file_equals_form_with_spaces(
    tmp_path: pathlib.Path,
) -> None:
    """Quoted --body-file=VALUE with spaces in path must be reassembled, not truncated."""
    body_file = tmp_path / "my body with spaces.md"
    body_file.write_text(VALID_BODY)
    command = f'gh pr create --title "T" --body-file="{body_file}"'
    assert extract_body_from_command(command) == VALID_BODY


def test_extract_body_file_missing_path_returns_none() -> None:
    command = 'gh pr create --title "T" --body-file /nonexistent/path.md'
    assert extract_body_from_command(command) is None


def test_extract_body_file_shell_variable_returns_empty() -> None:
    """Shell variables like $bodyPath can't be resolved at hook time -- approve safely."""
    command = 'gh pr create --title "T" --body-file $bodyPath'
    assert extract_body_from_command(command) == ""


def test_extract_body_file_no_false_positive_in_title() -> None:
    command = 'gh pr create --title "use --body-file /tmp/x.md" --body "actual body"'
    extracted_body = extract_body_from_command(command)
    assert extracted_body == "actual body"


def test_no_false_positive_body_in_title_string_value() -> None:
    command = 'gh pr create --title \'use --body "x"\' --body "actual body"'
    assert extract_body_from_command(command) == "actual body"


def test_extract_body_from_body_equals_double_quote_form() -> None:
    command = 'gh pr create --title "T" --body="Some body text here."'
    assert extract_body_from_command(command) == "Some body text here."


def test_extract_body_from_body_equals_single_quote_form() -> None:
    command = "gh pr create --title 'T' --body='Some body text here.'"
    assert extract_body_from_command(command) == "Some body text here."


def test_extract_body_equals_shell_var_returns_empty() -> None:
    """Shell variable like --body=$bodyText cannot be resolved at hook time -- approve safely."""
    command = 'gh pr create --title "T" --body=$bodyText'
    assert extract_body_from_command(command) == ""


def test_extract_short_flag_equals_form() -> None:
    command = 'gh pr create --title "T" -b="Some body text here."'
    assert extract_body_from_command(command) == "Some body text here."


def test_extract_short_flag_shell_var_returns_empty() -> None:
    """Shell variable like -b=$var cannot be resolved at hook time -- approve safely."""
    command = 'gh pr create --title "T" -b=$bodyVar'
    assert extract_body_from_command(command) == ""


def test_validate_passes_complete_body() -> None:
    assert validate_pr_body(VALID_BODY) == []


def test_validate_blocks_missing_sections() -> None:
    violations = validate_pr_body("Some body text without required sections.\n" * 5)
    assert any(
        "Missing required section" in each_violation for each_violation in violations
    )


def test_validate_blocks_vague_language() -> None:
    body = VALID_BODY + "\nFixed bug in the auth module.\n"
    violations = validate_pr_body(body)
    assert any("Vague language" in each_violation for each_violation in violations)


def test_validate_blocks_short_body() -> None:
    violations = validate_pr_body("Too short.")
    assert any("too short" in each_violation.lower() for each_violation in violations)


def test_body_file_content_validated(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text("Too short.")
    body = extract_body_from_command(
        f'gh pr create --title "T" --body-file {body_file}'
    )
    assert body == "Too short."
    violations = validate_pr_body(body)
    assert violations


def test_extract_body_string_value_skips_body_file_path_token() -> None:
    command = 'gh pr create --body-file --body "actual text"'
    assert extract_body_from_command(command) is None


def test_get_logical_first_line_does_not_join_bash_command_substitution() -> None:
    command = 'VAR=`cmd`\ngh pr create --body "text"'
    assert get_logical_first_line(command) == "VAR=`cmd`"


def test_get_logical_first_line_joins_powershell_backtick_continuation() -> None:
    command = 'Some-Command -Param `\n"value"'
    assert get_logical_first_line(command) == 'Some-Command -Param "value"'


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
