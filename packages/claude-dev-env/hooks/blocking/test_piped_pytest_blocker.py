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

ALL_KEYWORD_COMPOUND_PYTEST_COMMANDS = [
    "if true; then pytest tests; fi | tee run.log",
    "while true; do pytest tests; done | tee run.log",
    "for x in a; do pytest tests; done | tee run.log",
    "if false; then echo skip; else pytest tests; fi | tee run.log",
]

ALL_EARLIER_BRANCH_PYTEST_COMMANDS = [
    "if true; then pytest tests; else echo skip; fi | tee run.log",
    "if true; then pytest tests; elif false; then echo b; fi | tee run.log",
    "if true; then echo start; pytest tests; else echo skip; fi | tee run.log",
    "if a; then echo x; elif b; then pytest tests; else echo y; fi | tee run.log",
]

ALL_REDIRECTED_CLOSER_PYTEST_COMMANDS = [
    "if true; then pytest tests; fi 2>&1 | tee run.log",
    "if true; then pytest tests; fi > out.log | tee run.log",
    "while read x; do pytest $x; done < list | tee run.log",
    "{ pytest tests; } 2>&1 | tee run.log",
    "{ pytest tests; } >> out.log | tee run.log",
]

SCRIPT_OPERAND_CARRYING_A_MODULE_FLAG = "python myscript.py -m pytest | tee run.log"
ALL_INTERPRETER_MODULE_RUN_PYTEST_COMMANDS = [
    "python -m pytest tests | tee run.log",
    "python -mpytest tests | tee run.log",
    "python -m pytest tests --junitxml=r#1.xml | tee run.log",
    "python -X dev -m pytest tests | tee run.log",
    "python -W ignore -m pytest tests | tee run.log",
    "python -Xdev -m pytest tests | tee run.log",
    "python -u -m pytest tests | tee run.log",
    "python -B -m pytest tests | tee run.log",
    "python -OO -m pytest tests | tee run.log",
    "python --check-hash-based-pycs always -m pytest tests | tee run.log",
    "pypy3 --jit off -m pytest tests | tee run.log",
    "sudo python -m pytest tests | tee run.log",
    "uv run python -m pytest tests | tee run.log",
    "uvx python -m pytest tests | tee run.log",
    "coverage run -m pytest tests | tee run.log",
    "poetry run python -m pytest tests | tee run.log",
]

WRAPPER_CARRYING_THE_ONLY_PIPE = "bash -c 'python -m pytest tests | tee wrapped.log'"

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

ALL_CLUSTERED_SHORT_OPTION_PYTEST_COMMANDS = [
    "sudo -nu ci pytest tests | tee run.log",
    "sudo -nuci pytest tests | tee run.log",
]

ALL_SHELL_OPTION_VALUE_PYTEST_COMMANDS = [
    "bash -o pipefail -c 'pytest tests | tee run.log'",
    "bash -euo pipefail -c 'pytest tests | tee run.log'",
    "pwsh -ExecutionPolicy Bypass -Command 'pytest tests | tee run.log'",
]

ALL_CLUSTERED_STRING_EXEC_PYTEST_COMMANDS = [
    "bash -euc 'pytest tests | tee run.log'",
    "bash -ec 'pytest tests | tee run.log'",
    "bash -xc 'pytest tests | tee run.log'",
    "bash -ceu 'pytest tests | tee run.log'",
    "sh -ec 'pytest tests | tee run.log'",
    "bash -euoc pipefail 'pytest tests | tee run.log'",
]

ALL_COVERAGE_RUN_PYTEST_COMMANDS = [
    "coverage run -m pytest tests | tee run.log",
    "coverage run pytest tests | tee run.log",
]

ALL_TOOL_RUNNER_WRAPPER_PYTEST_COMMANDS = [
    "uvx pytest tests | tee run.log",
    "uvx --from pytest-xdist pytest tests | tee run.log",
    "uv tool run pytest tests | tee run.log",
    "uv tool run --from pytest-xdist pytest tests | tee run.log",
    "pdm run pytest tests | tee run.log",
    "hatch run pytest tests | tee run.log",
    "rye run pytest tests | tee run.log",
]

ALL_ALTERNATE_INTERPRETER_PYTEST_COMMANDS = [
    "python3.13t -m pytest tests | tee run.log",
    "pypy3 -m pytest tests | tee run.log",
    "pythonw -m pytest tests | tee run.log",
    "pyw -m pytest tests | tee run.log",
    "pythonw3.13.exe -m pytest tests | tee run.log",
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

HEREDOC_BODY_LINE_SPACED_LIKE_ITS_TERMINATOR = (
    "cat > run.sh <<EOF\n  EOF  \npytest tests | tee out.log\nEOF"
)
LIVE_RUN_BELOW_A_SPACED_TERMINATOR_LOOKALIKE = (
    f"{HEREDOC_BODY_LINE_SPACED_LIKE_ITS_TERMINATOR}\npytest tests | tee live.log"
)
LIVE_RUN_BELOW_A_TAB_INDENTED_TERMINATOR = (
    "cat > run.sh <<-EOF\npytest tests | tee out.log\n\tEOF\npytest tests | tee live.log"
)

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
    "bash scripts/ci.sh -c 'pytest tests'",
    "pwsh -File run.ps1 -c 'pytest tests' | tee run.log",
    "sudo -nu ci apt update | tee log",
    "sudo -nuci apt update | tee log",
    "coverage run -m mypy . | tee types.log",
    "coverage run --source pytest -m mypy . | tee types.log",
    "pyright -m pytest . | tee out.log",
    "bash -Cu scripts/ci.sh | tee run.log",
    "bash -eux scripts/ci.sh | tee run.log",
    "pwsh -NonInteractive -File run.ps1 | tee run.log",
    "uvx mypy . | tee types.log",
    "uv tool install pytest | tee install.log",
    "pdm run mypy . | tee types.log",
    "ls done | tee log",
    "tar -cf out.tar done | tee log",
    "echo fi | tee log",
    "echo esac | tee log",
    "ls do | tee log",
    "ls else | tee log",
    "if pytest tests; then echo ok; fi | tee run.log",
    "if cd repo && pytest tests; then echo ok; fi | tee run.log",
    "until pytest tests; do echo retry; done | tee run.log",
    "while pytest tests; do echo again; done | tee run.log",
    "if a; then echo x; elif pytest tests; then echo b; fi | tee run.log",
    "if true; then pytest tests; echo after; else echo skip; fi | tee run.log",
    "if a; then pytest tests; fi; if b; then echo c; fi | tee run.log",
    "{ pytest tests; }; if b; then echo c; else echo d; fi | tee run.log",
    "pytest tests; { echo a; } | tee run.log",
    "python -c 'import os' -m pytest tests | tee run.log",
    "python -Wu ignore -m pytest tests | tee run.log",
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


@pytest.mark.parametrize("each_command", ALL_KEYWORD_COMPOUND_PYTEST_COMMANDS)
def test_denies_a_keyword_compound_whose_last_command_is_pytest(each_command: str) -> None:
    """``fi`` and ``done`` end a compound, so the pipe after one reads pytest's code."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_EARLIER_BRANCH_PYTEST_COMMANDS)
def test_denies_a_compound_whose_earlier_branch_runs_pytest(each_command: str) -> None:
    """A branch other than the last one still runs, so its exit code reaches the pipe."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_REDIRECTED_CLOSER_PYTEST_COMMANDS)
def test_denies_a_compound_whose_closer_carries_a_redirection(each_command: str) -> None:
    """A redirection binds to the compound, so the closer before it still closes it."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


def test_allows_a_module_flag_that_belongs_to_a_script_operand() -> None:
    """A script path ends the interpreter's options, so its own ``-m pytest`` runs nothing."""
    assert find_piped_pytest_violation(SCRIPT_OPERAND_CARRYING_A_MODULE_FLAG) is None


@pytest.mark.parametrize("each_command", ALL_INTERPRETER_MODULE_RUN_PYTEST_COMMANDS)
def test_denies_an_interpreter_module_run_of_pytest(each_command: str) -> None:
    """An interpreter's own ``-m pytest`` still denies, glued or behind a valued option."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


def test_denies_a_pipe_carried_only_inside_a_wrapper_command_string() -> None:
    """The pipe prefilter reads the whole command, so a wrapper's inner pipe still counts."""
    assert find_piped_pytest_violation(WRAPPER_CARRYING_THE_ONLY_PIPE) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_FLAGGED_WRAPPER_PYTEST_COMMANDS)
def test_denies_a_pytest_run_behind_a_wrapper_carrying_its_own_flags(each_command: str) -> None:
    """A wrapper's own flags sit before the program, so the run behind them still counts."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_CLUSTERED_SHORT_OPTION_PYTEST_COMMANDS)
def test_denies_a_pytest_run_behind_a_clustered_short_option_wrapper(each_command: str) -> None:
    """A cluster ending in a value-taking flag takes the token after it, not the program."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_SHELL_OPTION_VALUE_PYTEST_COMMANDS)
def test_denies_a_wrapped_pytest_run_behind_a_shell_option_carrying_a_value(
    each_command: str,
) -> None:
    """A shell option's value is not the operand, so the string-exec flag behind it counts."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_CLUSTERED_STRING_EXEC_PYTEST_COMMANDS)
def test_denies_a_wrapped_pytest_run_behind_a_clustered_string_exec_flag(
    each_command: str,
) -> None:
    """A POSIX shell reads the ``-c`` inside ``-euc``, so the string behind it is a command."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_COVERAGE_RUN_PYTEST_COMMANDS)
def test_denies_a_pytest_run_behind_a_coverage_run_wrapper(each_command: str) -> None:
    """``coverage run`` exits with the program's code, so the pytest behind it counts."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_TOOL_RUNNER_WRAPPER_PYTEST_COMMANDS)
def test_denies_a_pytest_run_behind_a_tool_runner_wrapper(each_command: str) -> None:
    """Each tool runner exits with the program's code, so the pytest behind it counts."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_ALTERNATE_INTERPRETER_PYTEST_COMMANDS)
def test_denies_a_pytest_module_run_under_an_alternate_interpreter(each_command: str) -> None:
    """A free-threaded build and PyPy run the module the same way CPython does."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


def test_allows_a_heredoc_whose_body_line_is_its_terminator_with_surrounding_spaces() -> None:
    """Bash closes a ``<<`` heredoc on the exact word only, so a spaced lookalike is body text."""
    assert find_piped_pytest_violation(HEREDOC_BODY_LINE_SPACED_LIKE_ITS_TERMINATOR) is None


def test_denies_a_live_run_below_a_heredoc_a_spaced_lookalike_did_not_close() -> None:
    """Scanning resumes at the exact terminator, so the run under it is live and denies."""
    assert (
        find_piped_pytest_violation(LIVE_RUN_BELOW_A_SPACED_TERMINATOR_LOOKALIKE)
        == CORRECTIVE_MESSAGE
    )


def test_denies_a_live_run_below_a_tab_indented_terminator_that_closes_its_heredoc() -> None:
    """``<<-`` strips leading tabs, so a tab-indented terminator still closes the body."""
    assert (
        find_piped_pytest_violation(LIVE_RUN_BELOW_A_TAB_INDENTED_TERMINATOR) == CORRECTIVE_MESSAGE
    )


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
