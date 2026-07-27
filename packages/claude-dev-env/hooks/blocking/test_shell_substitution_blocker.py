"""Tests for shell_substitution_blocker hook."""

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "shell_substitution_blocker.py"


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def test_denies_dollar_paren_substitution() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": 'echo "head: $(git rev-parse HEAD)"'},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "shell-substitution"
        in response["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_denies_unescaped_backtick_substitution() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo `date`"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_plain_command_without_substitution() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git rev-parse HEAD"},
    }
    assert _run_hook(payload).stdout == ""


def test_allows_escaped_backtick_in_prose() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": r'echo "use \`foo\` like this"'},
    }
    assert _run_hook(payload).stdout == ""


def test_ignores_non_bash_tool() -> None:
    payload = {
        "tool_name": "Edit",
        "tool_input": {"command": 'echo "$(date)"'},
    }
    assert _run_hook(payload).stdout == ""


def test_denies_double_backslash_backtick_bypass() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": r"echo \\`date`"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_dollar_paren_inside_single_quotes() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo '$(not-executed)'"},
    }
    assert _run_hook(payload).stdout == ""


def test_allows_backtick_inside_single_quotes() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo '`not-executed`'"},
    }
    assert _run_hook(payload).stdout == ""


def test_denies_input_process_substitution() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "diff <(cat a) <(cat b)"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_output_process_substitution() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "tee >(gzip > out.gz)"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_process_substitution_inside_single_quotes() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo '<(not-executed)'"},
    }
    assert _run_hook(payload).stdout == ""


def test_allows_arithmetic_expansion() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $((2+2))"},
    }
    assert _run_hook(payload).stdout == ""
