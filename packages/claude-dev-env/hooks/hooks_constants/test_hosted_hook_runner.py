"""Behavior tests for the shared in-process hosted-hook runner.

Each test writes a real probe hook to a temp directory, runs it through
run_hook_capturing_output, and asserts on the captured stdout, the crash flag,
and the restoration of the interpreter's stdin, stdout, and argv.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from hooks_constants.hosted_hook_runner import HostedHookRun, run_hook_capturing_output  # noqa: E402


def _write_probe(tmp_path: Path, body: str) -> str:
    """Write a probe hook script and return its absolute path."""
    probe_path = tmp_path / "probe_hook.py"
    probe_path.write_text(body, encoding="utf-8")
    return str(probe_path)


def test_captures_stdout_from_a_printing_hook(tmp_path: Path) -> None:
    """The runner captures what a hook prints to stdout without a crash."""
    printed_payload = json.dumps({"hookSpecificOutput": {"permissionDecision": "deny"}})
    probe_path = _write_probe(tmp_path, f"print({printed_payload!r})\n")
    hook_run = run_hook_capturing_output(probe_path, "{}")
    assert hook_run.captured_stdout.strip() == printed_payload
    assert hook_run.did_crash is False


def test_hook_reads_the_swapped_stdin(tmp_path: Path) -> None:
    """A hook reading stdin sees the payload the runner replays."""
    probe_path = _write_probe(
        tmp_path,
        "import json\nimport sys\nprint(json.load(sys.stdin)['tool_name'])\n",
    )
    hook_run = run_hook_capturing_output(probe_path, json.dumps({"tool_name": "Bash"}))
    assert hook_run.captured_stdout.strip() == "Bash"
    assert hook_run.did_crash is False


def test_sets_argv_to_the_hook_script_path(tmp_path: Path) -> None:
    """The runner sets argv to the hook's own path so argv-branching hooks behave."""
    argv_result_path = tmp_path / "observed_argv.json"
    probe_path = _write_probe(
        tmp_path,
        "import json\nimport sys\nfrom pathlib import Path\n"
        f"Path({str(argv_result_path)!r}).write_text(json.dumps(sys.argv), encoding='utf-8')\n",
    )
    run_hook_capturing_output(probe_path, "{}")
    observed_argv = json.loads(argv_result_path.read_text(encoding="utf-8"))
    assert observed_argv == [probe_path]


def test_restores_stdin_stdout_and_argv_after_the_run(tmp_path: Path) -> None:
    """The runner restores stdin, stdout, and argv to their pre-call objects."""
    probe_path = _write_probe(tmp_path, "print('anything')\n")
    original_stdin = sys.stdin
    original_stdout = sys.stdout
    original_argv = sys.argv
    run_hook_capturing_output(probe_path, "{}")
    assert sys.stdin is original_stdin
    assert sys.stdout is original_stdout
    assert sys.argv is original_argv


def test_crash_reports_did_crash_and_does_not_propagate(tmp_path: Path) -> None:
    """A hook that raises is contained: did_crash is True and no exception escapes."""
    probe_path = _write_probe(tmp_path, "raise ValueError('boom')\n")
    hook_run = run_hook_capturing_output(probe_path, "{}")
    assert hook_run.did_crash is True
    assert hook_run.captured_stdout == ""


def test_system_exit_zero_after_output_is_captured(tmp_path: Path) -> None:
    """A hook that prints then exits zero returns its output and is not a crash."""
    probe_path = _write_probe(tmp_path, "print('decided')\nimport sys\nsys.exit(0)\n")
    hook_run = run_hook_capturing_output(probe_path, "{}")
    assert hook_run.captured_stdout.strip() == "decided"
    assert hook_run.did_crash is False


def test_system_exit_nonzero_without_output_is_not_a_crash(tmp_path: Path) -> None:
    """A clean nonzero SystemExit yields no output and is not treated as a crash."""
    probe_path = _write_probe(tmp_path, "import sys\nsys.exit(2)\n")
    hook_run = run_hook_capturing_output(probe_path, "{}")
    assert hook_run.did_crash is False
    assert hook_run.captured_stdout == ""


def test_returns_a_hosted_hook_run_instance(tmp_path: Path) -> None:
    """The runner returns a HostedHookRun carrying the two observable fields."""
    probe_path = _write_probe(tmp_path, "print('x')\n")
    hook_run = run_hook_capturing_output(probe_path, "{}")
    assert isinstance(hook_run, HostedHookRun)
