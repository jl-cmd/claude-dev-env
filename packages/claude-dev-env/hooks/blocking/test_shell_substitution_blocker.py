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


def test_allows_arithmetic_expansion_with_nested_parens() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $(( (1+2) * 3 ))"},
    }
    assert _run_hook(payload).stdout == ""


def test_allows_arithmetic_expansion_whose_body_bash_itself_rejects() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $((echo hi))"},
    }
    assert _run_hook(payload).stdout == ""


def test_allows_arithmetic_lookalike_inside_single_quotes() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo '$((cd /tmp) && pwd)'"},
    }
    assert _run_hook(payload).stdout == ""


def test_denies_subshell_disguised_as_arithmetic_expansion() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $((cd /tmp) && pwd)"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_parenthesized_command_word_disguised_as_arithmetic() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $((1+2) )"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_command_substitution_nested_inside_arithmetic_expansion() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $(( $(id -u) + 1 ))"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_backtick_substitution_nested_inside_arithmetic_expansion() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $(( `id -u` + 1 ))"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_nested_command_substitution_without_arithmetic() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo $(echo $(whoami))"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_backtick_inside_single_quoted_heredoc_body() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "cat > notes.md <<'EOF'\n"
                "reStructuredText markup: ``inert literal``\n"
                "EOF"
            )
        },
    }
    assert _run_hook(payload).stdout == ""


def test_allows_backtick_inside_tab_stripped_quoted_heredoc_body() -> None:
    """A ``<<-`` opener closes on a tab-indented terminator, and stays inert.

    The tab-strip rule decides which line ends the body. Getting it wrong
    swallows the rest of the command or ends the body early, so the branch is
    pinned here as well as in the shared pipeline that owns the rule.
    """
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "cat > notes.md <<-'EOF'\n"
                "reStructuredText markup: ``inert literal``\n"
                "\tEOF\n"
                "echo done"
            )
        },
    }
    assert _run_hook(payload).stdout == ""


def test_denies_backtick_inside_bare_heredoc_body() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "cat > notes.md <<EOF\nnow: `date`\nEOF"},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_command_substitution_inside_bare_heredoc_body() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "cat > notes.md <<EOF\nhead: $(git rev-parse HEAD)\nEOF"
        },
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_live_substitution_outside_a_quoted_heredoc() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "cat > notes.md <<'EOF'\n"
                "inert ``literal``\n"
                "EOF\n"
                'echo "$(git rev-parse HEAD)"'
            )
        },
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_backslash_escaped_heredoc_delimiter_body() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "cat > notes.md <<\\EOF\ninert `text`\nEOF"
        },
    }
    assert _run_hook(payload).stdout == ""


def test_denies_a_substitution_below_an_opener_inside_a_quoted_string() -> None:
    """An opener spelled inside a quoted string opens no heredoc.

    Bash runs the second line here. Reading the first line as an opener and
    dropping everything below it hides a live substitution from the scan.
    """
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": 'echo "<<\'EOF\'"\necho $(whoami)'},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_that_bypass_even_when_a_terminator_line_follows() -> None:
    """A terminator line below the substitution does not make the strip safe."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": 'echo "<<\'EOF\'"\necho $(whoami)\nEOF'},
    }
    response = json.loads(_run_hook(payload).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
