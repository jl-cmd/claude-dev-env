"""Tests for the piped-pytest Bash blocker.

The deny cases each carry a pytest spelling whose output feeds a pipe; the allow
cases each carry a pytest or pipe shape that keeps the pytest exit code. The
dispatcher case drives the payload through the hosted-hook chain, so it holds
only while the roster carries the segment.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_DIR = str(_BLOCKING_DIR.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
_BLOCKING_DIR_TEXT = str(_BLOCKING_DIR)
if _BLOCKING_DIR_TEXT not in sys.path:
    sys.path.insert(0, _BLOCKING_DIR_TEXT)

from hooks_constants.piped_pytest_blocker_constants import (  # noqa: E402
    CORRECTIVE_MESSAGE,
)
from hooks_constants.shell_command_segments import split_into_segments  # noqa: E402
from piped_pytest_blocker import (  # noqa: E402
    find_piped_pytest_violation,
    segment_runs_pytest,
)

SCRIPT_PATH = _BLOCKING_DIR / "piped_pytest_blocker.py"
DISPATCHER_PATH = _BLOCKING_DIR / "bash_pre_tool_use_dispatcher.py"
QUOTED_PIPE_COMMAND = 'pytest -k "a|b"'
SHARED_SPLITTER_SEGMENTS_FOR_QUOTED_PIPE = [["pytest", "-k", "a"], ["b"]]

ALL_PIPED_PYTEST_COMMANDS = [
    "pytest tests | tee run.log",
    "python -m pytest tests | head -50",
    r"C:\Python313\python.exe -m pytest tests | tee run.log",
    "python -m pytest tests 2>&1 | tee run.log",
    "cd packages/claude-dev-env && pytest | cat",
    "(python -m pytest tests) | tee run.log",
    "(python -m pytest tests)|tee run.log",
    "(python -m pytest tests)|&tee run.log",
    "(python -m pytest tests)|(tee run.log)",
    "(python -m pytest tests)|&(tee run.log)",
    "((python -m pytest tests))|(tee run.log)",
    'cmd /c "python -m pytest tests | tee run.log"',
    'cmd.exe /C "pytest tests | tee run.log"',
    "cmd /c python -m pytest tests | tee run.log",
    "cmd.exe /c python -m pytest | cat",
    "bash -c python -m pytest tests | tee run.log",
    "pwsh -Command python -m pytest tests | tee run.log",
    "pytest tests#tag | tee run.log",
    "python -m pytest tests --junitxml=r#1.xml | tee run.log",
    "bash -c 'pytest | tee run.log'",
    "bash -c 'pytest tests | tee x'",
    "python -mpytest tests | tee run.log",
    "time pytest tests | tee run.log",
]

ALL_BRACE_GROUP_PYTEST_COMMANDS = [
    "{ pytest tests; } | tee run.log",
    "{ python -m pytest tests; }|tee run.log",
    "{ echo start; pytest tests; } | tee run.log",
]

ALL_WINDOWS_SHIM_PYTEST_COMMANDS = [
    "pytest.bat tests | tee run.log",
    "pytest.cmd tests | tee run.log",
    "py.test.bat tests | tee run.log",
    "py.test.cmd tests | tee run.log",
    "python.bat -m pytest tests | tee run.log",
    "python.cmd -m pytest tests | tee run.log",
]

ALL_PASS_THROUGH_WRAPPER_PYTEST_COMMANDS = [
    "sudo pytest tests | tee run.log",
    "uv run pytest tests | tee run.log",
    "poetry run pytest tests | tee run.log",
    "pipenv run pytest tests | tee run.log",
    "uv run python -m pytest tests | tee run.log",
]

ALL_FLAGGED_WRAPPER_PYTEST_COMMANDS = [
    "uv run --frozen pytest tests | tee run.log",
    "uv run --no-sync pytest tests | tee run.log",
    "poetry run --no-plugins pytest tests | tee run.log",
    "uv run --python 3.13 pytest tests | tee run.log",
    "uv run -- pytest tests | tee run.log",
    "sudo -n pytest tests | tee run.log",
    "sudo -u ci pytest tests | tee run.log",
    "sudo -- pytest tests | tee run.log",
]

MULTI_LINE_SUBSHELL_PYTEST_COMMAND = "(\npython -m pytest tests\n) | tee run.log"
SUBSHELL_WRITING_A_PIPED_PYTEST_HEREDOC = (
    "(\ncat > run.sh <<'EOF'\npytest tests | tee out.log\nEOF\n) | tee wrote.log"
)
SUBSHELL_CARRYING_A_COMMENT_LINE = "(\n# the fast run\npython -m pytest tests\n) | tee run.log"
SUBSHELL_CARRYING_A_TRAILING_COMMENT = "(\npython -m pytest tests  # fast\n) | tee run.log"
COMMENT_CARRYING_A_STRAY_OPEN_PAREN = "# rerun the failing case (see the note\npytest | tee run.log"
COMMENT_NAMING_A_HEREDOC_OPENER = "# write it with <<EOF next time\npytest tests | tee run.log"
TRAILING_COMMENT_NAMING_A_HEREDOC_OPENER = (
    "echo hi  # cat <<EOF\npython -m pytest tests | tee run.log"
)

ALL_NESTED_MODULE_PYTEST_COMMANDS = [
    "python -m coverage run -m pytest tests | tee run.log",
    "python -m debugpy -m pytest tests | tee out.log",
]

ALL_WRAPPED_PYTEST_COMMANDS_PIPED_FROM_OUTSIDE = [
    "bash -c 'pytest tests' | tee run.log",
    "pwsh -Command 'pytest tests' | tee run.log",
]

ALL_HEREDOC_OPENER_SPELLINGS = ["<<EOF", "<<'EOF'", '<<"EOF"', "<<-EOF"]
HEREDOC_SCRIPT_TEMPLATE = "cat > run.sh {opener}\npytest tests | tee out.log\nEOF"

ALL_WIDE_HEREDOC_DELIMITERS = ["END-OF-TEST", "EOF-2.1", "run.sh-1", "EOF2"]
ALL_WIDE_HEREDOC_SCRIPT_TEMPLATES = [
    "cat > run.sh <<{delimiter}\npytest tests | tee out.log\n{delimiter}",
    "cat > run.sh <<'{delimiter}'\npytest tests | tee out.log\n{delimiter}",
    'cat > run.sh <<"{delimiter}"\npytest tests | tee out.log\n{delimiter}',
    "cat > run.sh <<-{delimiter}\npytest tests | tee out.log\n{delimiter}",
    "cat > run.sh <<\\{delimiter}\npytest tests | tee out.log\n{delimiter}",
]
HERE_STRING_ABOVE_A_PIPED_PYTEST_RUN = "cat file <<<word\npytest tests | tee run.log"
COMMAND_AFTER_A_HEREDOC = "cat > run.sh <<'EOF'\necho hi\nEOF\npytest tests | tee out.log"

ALL_LINE_CONTINUATION_TERMINATORS = ["\r\n", "\r", "\n"]

ALL_EXIT_CODE_PRESERVING_COMMANDS = [
    "pytest tests",
    "python -m pytest tests > run.log 2>&1",
    "git status --short | head -20",
    "cat ids.txt | pytest --stdin",
    "pytest tests && echo done | tee run.log",
    "python -m mypy . | tee types.log",
    "pytest tests -q\ngit status | head",
    """bash -c 'pytest -k "a|b"'""",
    "pytest tests >| run.log",
    "(pytest tests)||echo failed",
    "pytest tests  # | tee run.log",
    "cmd /c python -m mypy . | tee types.log",
    "cmd /c python -m pytest tests > run.log 2>&1",
    "bash -c 'git status' | tee status.log",
    "bash scripts/ci.sh -c 'pytest tests' | tee run.log",
    "sh scripts/ci.sh -lc 'pytest tests' | tee run.log",
    "cp file{a,b}.txt dst | tee log",
    "{ git status; } | tee run.log",
    "sudo apt update | tee log",
    "uv sync | tee build.log",
    "poetry run mypy . | tee types.log",
    "uv run --with pytest mypy . | tee types.log",
    "uv run --directory sub mypy . | tee types.log",
    "sudo -u pytest apt update | tee log",
    "bash -- -c 'pytest tests' | tee run.log",
]


def _run_process(script_path: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def _bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _deny_reason_from_stdout(stdout_text: str) -> str:
    parsed_payload = json.loads(stdout_text)
    hook_specific = parsed_payload["hookSpecificOutput"]
    assert hook_specific["permissionDecision"] == "deny"
    return hook_specific["permissionDecisionReason"]


@pytest.mark.parametrize("each_command", ALL_PIPED_PYTEST_COMMANDS)
def test_denies_a_pytest_run_feeding_a_pipe(each_command: str) -> None:
    """Each covered pytest spelling returns the deny message when it feeds a pipe."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_EXIT_CODE_PRESERVING_COMMANDS)
def test_allows_a_command_that_keeps_the_pytest_exit_code(each_command: str) -> None:
    """Bare pytest, redirection-only pytest, and unrelated pipes stay allowed."""
    assert find_piped_pytest_violation(each_command) is None


@pytest.mark.parametrize("each_command", ALL_NESTED_MODULE_PYTEST_COMMANDS)
def test_denies_pytest_named_by_a_later_module_flag(each_command: str) -> None:
    """A runner module ahead of ``-m pytest`` still leaves pytest as the run."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_WRAPPED_PYTEST_COMMANDS_PIPED_FROM_OUTSIDE)
def test_denies_a_wrapped_pytest_run_piped_from_outside(each_command: str) -> None:
    """A shell wrapper exits with pytest's code, so a pipe after it hides a failure."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_opener", ALL_HEREDOC_OPENER_SPELLINGS)
def test_allows_a_heredoc_that_writes_a_piped_pytest_line(each_opener: str) -> None:
    """A heredoc body is script text this call writes, not a command it runs."""
    script_writing_command = HEREDOC_SCRIPT_TEMPLATE.format(opener=each_opener)
    assert find_piped_pytest_violation(script_writing_command) is None


@pytest.mark.parametrize("each_template", ALL_WIDE_HEREDOC_SCRIPT_TEMPLATES)
@pytest.mark.parametrize("each_delimiter", ALL_WIDE_HEREDOC_DELIMITERS)
def test_allows_a_heredoc_whose_delimiter_carries_a_hyphen_digit_or_dot(
    each_delimiter: str, each_template: str
) -> None:
    """A shell takes any word as a delimiter, so the body below one stays script text."""
    script_writing_command = each_template.format(delimiter=each_delimiter)
    assert find_piped_pytest_violation(script_writing_command) is None


@pytest.mark.parametrize("each_command", ALL_BRACE_GROUP_PYTEST_COMMANDS)
def test_denies_a_brace_group_whose_last_command_is_pytest(each_command: str) -> None:
    """A brace group exits with its last command's code, so the pipe after it hides it."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_FLAGGED_WRAPPER_PYTEST_COMMANDS)
def test_denies_a_pytest_run_behind_a_wrapper_carrying_its_own_flags(each_command: str) -> None:
    """A wrapper's own flags sit before the program, so the run behind them still counts."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


def test_denies_a_piped_pytest_run_placed_below_a_here_string() -> None:
    """``<<<`` feeds one line rather than opening a body, so the lines under it run."""
    assert find_piped_pytest_violation(HERE_STRING_ABOVE_A_PIPED_PYTEST_RUN) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_WINDOWS_SHIM_PYTEST_COMMANDS)
def test_denies_a_windows_shim_spelling_of_a_pytest_run(each_command: str) -> None:
    """A ``.bat`` or ``.cmd`` shim runs the same suite as the bare spelling."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_PASS_THROUGH_WRAPPER_PYTEST_COMMANDS)
def test_denies_a_pytest_run_behind_a_pass_through_wrapper(each_command: str) -> None:
    """A wrapper exits with the program's code, so the pytest behind it still counts."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


def test_denies_a_piped_pytest_run_placed_after_a_heredoc_body() -> None:
    """Scanning resumes at the terminator, so a live pipe below it still denies."""
    assert find_piped_pytest_violation(COMMAND_AFTER_A_HEREDOC) == CORRECTIVE_MESSAGE


def test_denies_a_subshell_opened_and_closed_on_different_lines() -> None:
    """A parenthesis group spanning lines is one command, so the pipe after it denies."""
    assert find_piped_pytest_violation(MULTI_LINE_SUBSHELL_PYTEST_COMMAND) == CORRECTIVE_MESSAGE


def test_allows_a_subshell_whose_heredoc_body_carries_a_piped_pytest_line() -> None:
    """Body lines inside a grouped heredoc stay script text, so the group writes only."""
    assert find_piped_pytest_violation(SUBSHELL_WRITING_A_PIPED_PYTEST_HEREDOC) is None


def test_denies_a_subshell_whose_own_line_is_a_comment() -> None:
    """A comment line inside a group ends at its own newline, so the pipe after it denies."""
    assert find_piped_pytest_violation(SUBSHELL_CARRYING_A_COMMENT_LINE) == CORRECTIVE_MESSAGE


def test_denies_a_subshell_whose_pytest_line_ends_in_a_comment() -> None:
    """A trailing comment hides only the rest of its own line, not the lines below it."""
    assert find_piped_pytest_violation(SUBSHELL_CARRYING_A_TRAILING_COMMENT) == CORRECTIVE_MESSAGE


def test_denies_a_piped_pytest_line_below_a_comment_holding_an_open_paren() -> None:
    """A parenthesis inside a comment opens no group, so the next line still denies."""
    assert find_piped_pytest_violation(COMMENT_CARRYING_A_STRAY_OPEN_PAREN) == CORRECTIVE_MESSAGE


def test_denies_a_piped_pytest_line_below_a_comment_naming_a_heredoc_opener() -> None:
    """A ``<<WORD`` inside a comment opens no heredoc, so the line below stays live."""
    assert find_piped_pytest_violation(COMMENT_NAMING_A_HEREDOC_OPENER) == CORRECTIVE_MESSAGE


def test_denies_a_piped_pytest_line_below_a_trailing_comment_naming_a_heredoc_opener() -> None:
    """A ``<<WORD`` in a line's trailing comment opens no heredoc either."""
    assert (
        find_piped_pytest_violation(TRAILING_COMMENT_NAMING_A_HEREDOC_OPENER) == CORRECTIVE_MESSAGE
    )


@pytest.mark.parametrize("each_terminator", ALL_LINE_CONTINUATION_TERMINATORS)
def test_denies_a_continued_pytest_line_for_every_terminator(each_terminator: str) -> None:
    """A backslash continuation reads as one logical line for each line ending."""
    continued_command = f"python -m pytest tests \\{each_terminator}| tee run.log"
    assert find_piped_pytest_violation(continued_command) == CORRECTIVE_MESSAGE


def test_quoted_pipe_reads_as_unpiped_here_and_as_a_cut_by_the_shared_splitter() -> None:
    """One input, both readings: this hook allows it, the shared splitter cuts it.

    The shared splitter's segments for the input are pinned, so a quote-aware
    ``shell_command_segments`` turns this test red — the signal to move this
    module onto the shared helper.
    """
    assert find_piped_pytest_violation(QUOTED_PIPE_COMMAND) is None
    assert (
        split_into_segments(shlex.split(QUOTED_PIPE_COMMAND))
        == SHARED_SPLITTER_SEGMENTS_FOR_QUOTED_PIPE
    )


def test_segment_leading_with_pytest_is_recognized() -> None:
    """A segment whose program is pytest reads as a pytest run."""
    assert segment_runs_pytest(["pytest", "tests", "-q"]) is True


def test_segment_running_another_python_module_is_not_pytest() -> None:
    """An interpreter running a different module reads as no pytest run."""
    assert segment_runs_pytest(["python", "-m", "mypy", "."]) is False


def test_hook_emits_a_deny_payload_for_a_piped_pytest_run() -> None:
    """The standalone hook writes the deny message for a piped pytest command."""
    completed = _run_process(SCRIPT_PATH, _bash_payload("pytest tests | tee run.log"))
    assert _deny_reason_from_stdout(completed.stdout) == CORRECTIVE_MESSAGE


def test_deny_message_names_running_pytest_alone_and_the_exit_code() -> None:
    """The deny message states the fix and why the pipe hides a failure."""
    completed = _run_process(SCRIPT_PATH, _bash_payload("pytest | tee run.log"))
    deny_reason = _deny_reason_from_stdout(completed.stdout)
    assert "run pytest alone" in deny_reason.lower()
    assert "exit code" in deny_reason.lower()


def test_hook_stays_silent_on_a_bare_pytest_run() -> None:
    """A pytest command with no pipe produces no decision."""
    completed = _run_process(SCRIPT_PATH, _bash_payload("pytest tests"))
    assert completed.stdout == ""


def test_ignores_an_unsupported_tool_name() -> None:
    """A non-Bash tool payload produces no decision."""
    payload = {"tool_name": "Edit", "tool_input": {"command": "pytest | tee run.log"}}
    assert _run_process(SCRIPT_PATH, payload).stdout == ""


def test_ignores_a_payload_without_a_command() -> None:
    """A Bash payload carrying no command produces no decision."""
    assert _run_process(SCRIPT_PATH, {"tool_name": "Bash", "tool_input": {}}).stdout == ""


def test_dispatcher_denies_a_piped_pytest_run() -> None:
    """The hosted-hook chain surfaces the deny, so the roster carries the segment."""
    completed = _run_process(DISPATCHER_PATH, _bash_payload("pytest tests | tee run.log"))
    assert "exit code" in _deny_reason_from_stdout(completed.stdout).lower()
