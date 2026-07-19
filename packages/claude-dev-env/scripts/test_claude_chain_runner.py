"""Behavioral tests for the claude fallback-chain runner."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import claude_chain_runner as runner  # noqa: E402
import claude_chain_usage as chain_usage  # noqa: E402
from dev_env_scripts_constants.claude_chain_constants import (  # noqa: E402
    SESSION_AFFINITY_FILENAME,
    ALL_USAGE_LIMIT_SIGNATURES,
    ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
    ATTEMPT_STATUS_NONZERO_EXIT,
    ATTEMPT_STATUS_SERVED,
    ATTEMPT_STATUS_TIMEOUT,
    ATTEMPT_STATUS_USAGE_LIMITED,
    ATTEMPT_SUMMARY_ENTRY_TEMPLATE,
    ATTEMPT_SUMMARY_JOIN_SEPARATOR,
    CHAIN_CONFIG_ERROR_EXIT_CODE,
    CHAIN_EXHAUSTED_EXIT_CODE,
    CHAIN_EXHAUSTED_MESSAGE_TEMPLATE,
    CLAUDE_HOME_SUBDIRECTORY,
    CLI_ARGUMENTS_SEPARATOR,
    CLI_TIMEOUT_FLAG,
    CODEC_ERROR_STRATEGY,
    CONFIG_CHAIN_EMPTY_REASON,
    CONFIG_CHAIN_KEY,
    CONFIG_CHAIN_NOT_LIST_REASON,
    CONFIG_COMMAND_KEY,
    CONFIG_ENTRY_COMMAND_MISSING_REASON,
    CONFIG_ENTRY_EXTRA_ARGS_INVALID_REASON,
    CONFIG_ENTRY_NOT_OBJECT_REASON,
    CONFIG_EXTRA_ARGS_KEY,
    CONFIG_FILENAME,
    CONFIG_INVALID_SHAPE_MESSAGE_TEMPLATE,
    CONFIG_MALFORMED_MESSAGE_TEMPLATE,
    CONFIG_MISSING_MESSAGE_TEMPLATE,
    CONFIG_NOT_OBJECT_REASON,
    CONFIG_UNREADABLE_MESSAGE_TEMPLATE,
    DEFAULT_TIMEOUT_SECONDS,
    EXAMPLE_CONFIG_FILENAME,
    NO_COMPLETED_PROCESS_RETURN_CODE,
    UTF8_ENCODING,
)

_LARGE_CAPTURE_BYTE_COUNT = 400_000
_LARGE_CAPTURE_MARKER = "X"
_STDIN_ECHO_PAYLOAD = "charter body for spool path"
_UNDECODABLE_STDOUT_BYTES = b"ok \x90 end"
_DECODED_UNDECODABLE_STDOUT = "ok \ufffd end"
_CRLF_CHILD_STDOUT_BYTES = b"a\r\nb\rc\n"
_CRLF_CHILD_STDOUT_NORMALIZED = "a\nb\nc\n"

_A_SIGNATURE = ALL_USAGE_LIMIT_SIGNATURES[0]
_PROMPT_ARGUMENTS = ["-p", "hello"]
_EQUAL_WEEKLY_REMAINING_PERCENT = 50.0
_HIGH_WEEKLY_REMAINING_PERCENT = 90.0
_MID_WEEKLY_REMAINING_PERCENT = 50.0
_LOW_WEEKLY_REMAINING_PERCENT = 10.0


def _completed(command, returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=[command], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _entry(command, extra_args=None):
    return {
        CONFIG_COMMAND_KEY: command,
        CONFIG_EXTRA_ARGS_KEY: extra_args if extra_args is not None else [],
    }


def _write_chain_config(tmp_path, chain_entries):
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text(
        json.dumps({CONFIG_CHAIN_KEY: chain_entries}), encoding=UTF8_ENCODING
    )
    return config_file


def _config_order_usage_reporter(
    *, config_path: Path
) -> list[chain_usage.AccountUsageReport]:
    all_entries = runner.load_chain(config_path)
    return [
        chain_usage.AccountUsageReport(
            command=each_entry.command,
            weekly_remaining_percent=_EQUAL_WEEKLY_REMAINING_PERCENT,
        )
        for each_entry in all_entries
    ]


def _usage_reporter_from_remaining(
    remaining_percent_by_command: dict[str, float | None],
):
    call_count = {"count": 0}

    def active_reporter(
        *, config_path: Path
    ) -> list[chain_usage.AccountUsageReport]:
        call_count["count"] += 1
        all_entries = runner.load_chain(config_path)
        return [
            chain_usage.AccountUsageReport(
                command=each_entry.command,
                weekly_remaining_percent=remaining_percent_by_command[
                    each_entry.command
                ],
            )
            for each_entry in all_entries
        ]

    active_reporter.call_count = call_count
    return active_reporter


class _Recorder:
    def __init__(self, behavior_by_command):
        self.behavior_by_command = behavior_by_command
        self.invocations = []
        self.timeouts = []
        self.all_keyword_arguments = []

    def __call__(self, invocation, **keyword_arguments):
        self.invocations.append(invocation)
        self.timeouts.append(keyword_arguments.get("timeout"))
        self.all_keyword_arguments.append(keyword_arguments)
        behavior = self.behavior_by_command[invocation[0]]
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior


class _TtyStdin:
    def isatty(self) -> bool:
        return True


def _install_tty_stdin(monkeypatch):
    monkeypatch.setattr(runner.sys, "stdin", _TtyStdin())


def _install(
    monkeypatch,
    config_file,
    behavior_by_command,
    *,
    weekly_usage_reporter=None,
):
    recorder = _Recorder(behavior_by_command)
    monkeypatch.setattr(runner, "chain_config_path", lambda: config_file)
    monkeypatch.setattr(runner, "chain_subprocess_runner", recorder)
    active_reporter = (
        weekly_usage_reporter
        if weekly_usage_reporter is not None
        else _config_order_usage_reporter
    )
    monkeypatch.setattr(runner, "chain_weekly_usage_reporter", active_reporter)
    _install_tty_stdin(monkeypatch)
    return recorder


def test_highest_weekly_remaining_is_tried_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _LOW_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
        }
    )
    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 0, stdout="from-claude"),
            "claude-ev": _completed("claude-ev", 0, stdout="from-ev"),
        },
        weekly_usage_reporter=usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"
    assert chain_result.returncode == 0
    assert chain_result.stdout == "from-ev"
    assert recorder.invocations[0][0] == "claude-ev"
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude-ev"
    ]
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_SERVED


def test_usage_limit_failsover_remaining_ranked_accounts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(
        tmp_path, [_entry("claude"), _entry("claude-ev"), _entry("claude-editor")]
    )
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _MID_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
            "claude-editor": _LOW_WEEKLY_REMAINING_PERCENT,
        }
    )
    _install(
        monkeypatch,
        config_file,
        {
            "claude-ev": _completed("claude-ev", 1, stderr=_A_SIGNATURE),
            "claude": _completed("claude", 0, stdout="ok"),
            "claude-editor": _completed("claude-editor", 0, stdout="should not run"),
        },
        weekly_usage_reporter=usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert chain_result.returncode == 0
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude-ev",
        "claude",
    ]
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_USAGE_LIMITED
    assert chain_result.attempts[1].status == ATTEMPT_STATUS_SERVED


def test_non_usage_error_on_highest_ranked_stops_without_rest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _LOW_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
        }
    )
    _install(
        monkeypatch,
        config_file,
        {
            "claude-ev": _completed("claude-ev", 2, stderr="unknown flag"),
            "claude": _completed("claude", 0, stdout="should not run"),
        },
        weekly_usage_reporter=usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"
    assert chain_result.returncode == 2
    assert len(chain_result.attempts) == 1
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_NONZERO_EXIT


def test_weekly_usage_probe_runs_once_per_run_claude(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _HIGH_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _LOW_WEEKLY_REMAINING_PERCENT,
        }
    )
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 1, stderr=_A_SIGNATURE),
            "claude-ev": _completed("claude-ev", 0, stdout="ok"),
        },
        weekly_usage_reporter=usage_reporter,
    )
    runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert usage_reporter.call_count["count"] == 1


def test_usage_reporter_import_failure_falls_back_to_config_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])

    def broken_usage_reporter(
        *, config_path: Path
    ) -> list[chain_usage.AccountUsageReport]:
        raise ImportError("claude_chain_usage unavailable")

    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 0, stdout="from-claude"),
            "claude-ev": _completed("claude-ev", 0, stdout="from-ev"),
        },
        weekly_usage_reporter=broken_usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert chain_result.returncode == 0
    assert chain_result.stdout == "from-claude"
    assert recorder.invocations[0][0] == "claude"
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude"
    ]


def test_missing_high_remaining_binary_falls_through_to_lower_remaining(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _LOW_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
        }
    )
    _install(
        monkeypatch,
        config_file,
        {
            "claude-ev": FileNotFoundError(),
            "claude": _completed("claude", 0, stdout="from-claude"),
        },
        weekly_usage_reporter=usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert chain_result.returncode == 0
    assert chain_result.stdout == "from-claude"
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude-ev",
        "claude",
    ]
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
        ATTEMPT_STATUS_SERVED,
    ]


def test_all_missing_binaries_exhausts_chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _LOW_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
        }
    )
    _install(
        monkeypatch,
        config_file,
        {
            "claude-ev": FileNotFoundError(),
            "claude": FileNotFoundError(),
        },
        weekly_usage_reporter=usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command is None
    assert chain_result.returncode == NO_COMPLETED_PROCESS_RETURN_CODE
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude-ev",
        "claude",
    ]
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
        ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
    ]


def test_missing_later_ranked_binary_is_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(
        tmp_path, [_entry("claude"), _entry("claude-ev"), _entry("claude-editor")]
    )
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _MID_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
            "claude-editor": _LOW_WEEKLY_REMAINING_PERCENT,
        }
    )
    _install(
        monkeypatch,
        config_file,
        {
            "claude-ev": _completed("claude-ev", 1, stderr=_A_SIGNATURE),
            "claude": FileNotFoundError(),
            "claude-editor": _completed("claude-editor", 0, stdout="done"),
        },
        weekly_usage_reporter=usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude-editor"
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude-ev",
        "claude",
        "claude-editor",
    ]
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        ATTEMPT_STATUS_USAGE_LIMITED,
        ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
        ATTEMPT_STATUS_SERVED,
    ]


def test_ranked_walk_preserves_extra_args_for_mapped_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [
            _entry("claude", extra_args=["--account", "primary"]),
            _entry("claude-ev", extra_args=["--account", "ev"]),
        ],
    )
    usage_reporter = _usage_reporter_from_remaining(
        {
            "claude": _LOW_WEEKLY_REMAINING_PERCENT,
            "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
        }
    )
    recorder = _install(
        monkeypatch,
        config_file,
        {"claude-ev": _completed("claude-ev", 0)},
        weekly_usage_reporter=usage_reporter,
    )
    runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert recorder.invocations[0] == [
        "claude-ev",
        "-p",
        "hello",
        "--account",
        "ev",
    ]


def test_duplicate_command_entries_are_both_walked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [
            _entry("claude", extra_args=["--account", "primary"]),
            _entry("claude", extra_args=["--account", "secondary"]),
        ],
    )
    usage_reporter = _usage_reporter_from_remaining(
        {"claude": _HIGH_WEEKLY_REMAINING_PERCENT}
    )
    recorder = _install(
        monkeypatch,
        config_file,
        {"claude": _completed("claude", 1, stderr=_A_SIGNATURE)},
        weekly_usage_reporter=usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert [each_invocation[-1] for each_invocation in recorder.invocations] == [
        "primary",
        "secondary",
    ]
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        ATTEMPT_STATUS_USAGE_LIMITED,
        ATTEMPT_STATUS_USAGE_LIMITED,
    ]


def test_entry_absent_from_usage_report_is_still_walked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])

    def partial_usage_reporter(
        *, config_path: Path
    ) -> list[chain_usage.AccountUsageReport]:
        return [
            chain_usage.AccountUsageReport(
                command="claude-ev",
                weekly_remaining_percent=_HIGH_WEEKLY_REMAINING_PERCENT,
            )
        ]

    _install(
        monkeypatch,
        config_file,
        {
            "claude-ev": _completed("claude-ev", 1, stderr=_A_SIGNATURE),
            "claude": _completed("claude", 0, stdout="ok"),
        },
        weekly_usage_reporter=partial_usage_reporter,
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude-ev",
        "claude",
    ]


def test_usage_limited_primary_falls_over_to_second(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 1, stderr=_A_SIGNATURE),
            "claude-ev": _completed("claude-ev", 0, stdout="ok"),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"
    assert chain_result.returncode == 0
    assert chain_result.stdout == "ok"
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude",
        "claude-ev",
    ]
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_USAGE_LIMITED
    assert chain_result.attempts[1].status == ATTEMPT_STATUS_SERVED


def test_nonzero_exit_without_signature_does_not_fall_over(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 2, stderr="unknown flag"),
            "claude-ev": _completed("claude-ev", 0, stdout="should not run"),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert chain_result.returncode == 2
    assert len(chain_result.attempts) == 1
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_NONZERO_EXIT


def test_timeout_on_primary_does_not_fall_over(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": subprocess.TimeoutExpired(cmd=["claude"], timeout=5),
            "claude-ev": _completed("claude-ev", 0),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command is None
    assert chain_result.returncode == NO_COMPLETED_PROCESS_RETURN_CODE
    assert len(chain_result.attempts) == 1
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_TIMEOUT


def test_missing_primary_binary_falls_through_to_next(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": FileNotFoundError(),
            "claude-ev": _completed("claude-ev", 0, stdout="from-ev"),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"
    assert chain_result.returncode == 0
    assert chain_result.stdout == "from-ev"
    assert [each_attempt.command for each_attempt in chain_result.attempts] == [
        "claude",
        "claude-ev",
    ]
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
        ATTEMPT_STATUS_SERVED,
    ]


def test_missing_fallback_binary_is_skipped_and_walk_continues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(
        tmp_path, [_entry("claude"), _entry("claude-ev"), _entry("claude-editor")]
    )
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 1, stderr=_A_SIGNATURE),
            "claude-ev": FileNotFoundError(),
            "claude-editor": _completed("claude-editor", 0, stdout="done"),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude-editor"
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        ATTEMPT_STATUS_USAGE_LIMITED,
        ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
        ATTEMPT_STATUS_SERVED,
    ]


def test_zero_exit_mentioning_usage_limit_is_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 0, stdout=f"note: {_A_SIGNATURE} earlier"),
            "claude-ev": _completed("claude-ev", 0),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert chain_result.returncode == 0
    assert len(chain_result.attempts) == 1
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_SERVED


def test_exhausted_chain_records_every_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 1, stderr=_A_SIGNATURE),
            "claude-ev": _completed("claude-ev", 1, stderr=_A_SIGNATURE),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command is None
    assert chain_result.returncode == 1
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        ATTEMPT_STATUS_USAGE_LIMITED,
        ATTEMPT_STATUS_USAGE_LIMITED,
    ]


def test_reordering_config_changes_walk_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    behavior_by_command = {
        "claude": _completed("claude", 0, stdout="from-claude"),
        "claude-ev": _completed("claude-ev", 0, stdout="from-ev"),
    }
    first_config = tmp_path / "first"
    first_config.mkdir()
    config_a = _write_chain_config(
        first_config, [_entry("claude"), _entry("claude-ev")]
    )
    _install(monkeypatch, config_a, behavior_by_command)
    result_a = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert result_a.served_command == "claude"

    second_config = tmp_path / "second"
    second_config.mkdir()
    config_b = _write_chain_config(
        second_config, [_entry("claude-ev"), _entry("claude")]
    )
    _install(monkeypatch, config_b, behavior_by_command)
    result_b = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert result_b.served_command == "claude-ev"


def test_extra_args_are_appended_to_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(
        tmp_path, [_entry("claude", extra_args=["--account", "ev"])]
    )
    recorder = _install(monkeypatch, config_file, {"claude": _completed("claude", 0)})
    runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert recorder.invocations[0] == ["claude", "-p", "hello", "--account", "ev"]


def test_run_claude_forwards_stdin_text_to_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    recorder = _install(monkeypatch, config_file, {"claude": _completed("claude", 0)})
    runner.run_claude(
        _PROMPT_ARGUMENTS, timeout_seconds=5, stdin_text="charter body"
    )
    assert recorder.all_keyword_arguments[0]["input"] == "charter body"


def test_run_claude_passes_none_input_when_stdin_text_omitted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    recorder = _install(monkeypatch, config_file, {"claude": _completed("claude", 0)})
    runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert recorder.all_keyword_arguments[0].get("input") is None


def test_cli_forwards_piped_stdin_to_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    recorder = _install(monkeypatch, config_file, {"claude": _completed("claude", 0)})

    class _PipedStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return "charter body"

    monkeypatch.setattr(runner.sys, "stdin", _PipedStdin())
    exit_code = runner.main([CLI_ARGUMENTS_SEPARATOR, "-p", "hi"])
    assert exit_code == 0
    assert recorder.all_keyword_arguments[0]["input"] == "charter body"


def test_signature_matching_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 1, stderr=_A_SIGNATURE.upper()),
            "claude-ev": _completed("claude-ev", 0),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"


def test_cli_passthrough_builds_argument_list_and_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    recorder = _install(monkeypatch, config_file, {"claude": _completed("claude", 0)})
    exit_code = runner.main(
        [CLI_TIMEOUT_FLAG, "9", CLI_ARGUMENTS_SEPARATOR, "-p", "hi"]
    )
    assert exit_code == 0
    assert recorder.invocations[0] == ["claude", "-p", "hi"]
    assert recorder.timeouts[0] == 9


def test_cli_uses_default_timeout_when_flag_omitted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    recorder = _install(monkeypatch, config_file, {"claude": _completed("claude", 0)})
    runner.main([CLI_ARGUMENTS_SEPARATOR, "-p", "hi"])
    assert recorder.timeouts[0] == DEFAULT_TIMEOUT_SECONDS


def test_cli_served_nonzero_exit_is_passed_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    _install(
        monkeypatch,
        config_file,
        {"claude": _completed("claude", 7, stdout="out", stderr="err")},
    )
    exit_code = runner.main([CLI_ARGUMENTS_SEPARATOR, "-p", "hi"])
    captured = capsys.readouterr()
    assert exit_code == 7
    assert captured.out == "out"
    assert "err" in captured.err


def test_cli_exhausted_chain_exits_nonzero_with_attempt_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 1, stderr=_A_SIGNATURE),
            "claude-ev": _completed("claude-ev", 1, stderr=_A_SIGNATURE),
        },
    )
    exit_code = runner.main([CLI_ARGUMENTS_SEPARATOR, "-p", "hi"])
    captured = capsys.readouterr()
    assert exit_code == CHAIN_EXHAUSTED_EXIT_CODE
    expected_summary = ATTEMPT_SUMMARY_JOIN_SEPARATOR.join(
        ATTEMPT_SUMMARY_ENTRY_TEMPLATE.format(
            command=each_command, status=ATTEMPT_STATUS_USAGE_LIMITED
        )
        for each_command in ("claude", "claude-ev")
    )
    assert (
        CHAIN_EXHAUSTED_MESSAGE_TEMPLATE.format(attempt_summary=expected_summary)
        in captured.err
    )


def test_cli_missing_config_exits_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_config = tmp_path / CONFIG_FILENAME
    monkeypatch.setattr(runner, "chain_config_path", lambda: missing_config)
    _install_tty_stdin(monkeypatch)
    exit_code = runner.main([CLI_ARGUMENTS_SEPARATOR, "-p", "hi"])
    captured = capsys.readouterr()
    assert exit_code == CHAIN_CONFIG_ERROR_EXIT_CODE
    assert EXAMPLE_CONFIG_FILENAME in captured.err


def test_missing_config_raises_naming_path_and_example(tmp_path: Path) -> None:
    missing_config = tmp_path / CONFIG_FILENAME
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(missing_config)
    assert str(raised.value) == CONFIG_MISSING_MESSAGE_TEMPLATE.format(
        config_path=missing_config, example_filename=EXAMPLE_CONFIG_FILENAME
    )


def test_malformed_json_raises_configuration_error(tmp_path: Path) -> None:
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text("{ not valid json", encoding=UTF8_ENCODING)
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(config_file)
    malformed_prefix = CONFIG_MALFORMED_MESSAGE_TEMPLATE.split("{config_path}")[0]
    assert malformed_prefix in str(raised.value)
    assert EXAMPLE_CONFIG_FILENAME in str(raised.value)


def test_unreadable_config_raises_configuration_error(tmp_path: Path) -> None:
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text("{}", encoding=UTF8_ENCODING)
    with patch.object(Path, "read_text", side_effect=OSError("locked")):
        with pytest.raises(runner.ChainConfigurationError) as raised:
            runner.load_chain(config_file)
    unreadable_prefix = CONFIG_UNREADABLE_MESSAGE_TEMPLATE.split("{config_path}")[0]
    assert unreadable_prefix in str(raised.value)


def test_top_level_not_object_raises_invalid_shape(tmp_path: Path) -> None:
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text(json.dumps(["claude"]), encoding=UTF8_ENCODING)
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(config_file)
    assert str(raised.value) == CONFIG_INVALID_SHAPE_MESSAGE_TEMPLATE.format(
        config_path=config_file,
        reason=CONFIG_NOT_OBJECT_REASON,
        example_filename=EXAMPLE_CONFIG_FILENAME,
    )


def test_chain_key_not_list_raises_invalid_shape(tmp_path: Path) -> None:
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text(
        json.dumps({CONFIG_CHAIN_KEY: "claude"}), encoding=UTF8_ENCODING
    )
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(config_file)
    assert CONFIG_CHAIN_NOT_LIST_REASON in str(raised.value)


def test_empty_chain_raises_invalid_shape(tmp_path: Path) -> None:
    config_file = _write_chain_config(tmp_path, [])
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(config_file)
    assert CONFIG_CHAIN_EMPTY_REASON in str(raised.value)


def test_entry_not_object_raises_invalid_shape(tmp_path: Path) -> None:
    config_file = _write_chain_config(tmp_path, ["claude"])
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(config_file)
    assert CONFIG_ENTRY_NOT_OBJECT_REASON in str(raised.value)


def test_entry_without_command_raises_invalid_shape(tmp_path: Path) -> None:
    config_file = _write_chain_config(tmp_path, [{CONFIG_EXTRA_ARGS_KEY: []}])
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(config_file)
    assert CONFIG_ENTRY_COMMAND_MISSING_REASON in str(raised.value)


def test_entry_with_non_list_extra_args_raises_invalid_shape(tmp_path: Path) -> None:
    config_file = _write_chain_config(
        tmp_path, [{CONFIG_COMMAND_KEY: "claude", CONFIG_EXTRA_ARGS_KEY: "nope"}]
    )
    with pytest.raises(runner.ChainConfigurationError) as raised:
        runner.load_chain(config_file)
    assert CONFIG_ENTRY_EXTRA_ARGS_INVALID_REASON in str(raised.value)


def test_extra_args_default_to_empty_when_omitted(tmp_path: Path) -> None:
    config_file = _write_chain_config(tmp_path, [{CONFIG_COMMAND_KEY: "claude"}])
    all_entries = runner.load_chain(config_file)
    assert all_entries[0].command == "claude"
    assert all_entries[0].extra_args == ()


def test_load_chain_parses_command_and_extra_args(tmp_path: Path) -> None:
    config_file = _write_chain_config(
        tmp_path, [_entry("claude", extra_args=["--account", "ev"])]
    )
    all_entries = runner.load_chain(config_file)
    assert all_entries == [
        runner.ChainEntry(command="claude", extra_args=("--account", "ev"))
    ]


def test_chain_config_path_points_at_home_config() -> None:
    config_path = runner.chain_config_path()
    assert config_path.name == CONFIG_FILENAME
    assert CLAUDE_HOME_SUBDIRECTORY in config_path.parts


def test_real_subprocess_capture_replaces_undecodable_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry(sys.executable)])
    monkeypatch.setattr(runner, "chain_config_path", lambda: config_file)
    monkeypatch.setattr(
        runner, "chain_weekly_usage_reporter", _config_order_usage_reporter
    )
    child_code = 'import sys; sys.stdout.buffer.write(b"ok \\x90 end")'
    chain_result = runner.run_claude(["-c", child_code], timeout_seconds=60)
    assert chain_result.served_command == sys.executable
    assert chain_result.returncode == 0
    assert chain_result.stdout == "ok � end"


def test_real_subprocess_capture_preserves_utf8_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry(sys.executable)])
    monkeypatch.setattr(runner, "chain_config_path", lambda: config_file)
    monkeypatch.setattr(
        runner, "chain_weekly_usage_reporter", _config_order_usage_reporter
    )
    child_code = 'import sys; sys.stdout.buffer.write("report ✅ done".encode("utf-8"))'
    chain_result = runner.run_claude(["-c", child_code], timeout_seconds=60)
    assert chain_result.served_command == sys.executable
    assert chain_result.returncode == 0
    assert chain_result.stdout == "report ✅ done"


def test_run_captured_subprocess_spools_large_stdout_and_stderr() -> None:
    child_code = (
        "import sys;"
        f"sys.stdout.write({_LARGE_CAPTURE_MARKER!r} * {_LARGE_CAPTURE_BYTE_COUNT});"
        "sys.stderr.write('err-marker');"
        "sys.exit(3)"
    )
    completion = runner._run_captured_subprocess(
        [sys.executable, "-c", child_code],
        encoding=UTF8_ENCODING,
        errors=CODEC_ERROR_STRATEGY,
        timeout=60,
        check=False,
        input=None,
    )
    assert completion.returncode == 3
    assert len(completion.stdout) == _LARGE_CAPTURE_BYTE_COUNT
    assert completion.stdout == _LARGE_CAPTURE_MARKER * _LARGE_CAPTURE_BYTE_COUNT
    assert completion.stderr == "err-marker"


def test_run_captured_subprocess_forwards_stdin_input() -> None:
    child_code = "import sys; sys.stdout.write(sys.stdin.read())"
    completion = runner._run_captured_subprocess(
        [sys.executable, "-c", child_code],
        encoding=UTF8_ENCODING,
        errors=CODEC_ERROR_STRATEGY,
        timeout=60,
        check=False,
        input=_STDIN_ECHO_PAYLOAD,
    )
    assert completion.returncode == 0
    assert completion.stdout == _STDIN_ECHO_PAYLOAD
    assert completion.stderr == ""


def test_run_captured_subprocess_replaces_undecodable_stdout_bytes() -> None:
    child_code = (
        "import sys;"
        f"sys.stdout.buffer.write({_UNDECODABLE_STDOUT_BYTES!r})"
    )
    completion = runner._run_captured_subprocess(
        [sys.executable, "-c", child_code],
        encoding=UTF8_ENCODING,
        errors=CODEC_ERROR_STRATEGY,
        timeout=60,
        check=False,
        input=None,
    )
    assert completion.returncode == 0
    assert completion.stdout == _DECODED_UNDECODABLE_STDOUT


def test_run_captured_subprocess_normalizes_crlf_to_lf() -> None:
    """Spool decode matches subprocess text=True universal-newline translation."""
    child_code = (
        "import sys;"
        f"sys.stdout.buffer.write({_CRLF_CHILD_STDOUT_BYTES!r})"
    )
    completion = runner._run_captured_subprocess(
        [sys.executable, "-c", child_code],
        encoding=UTF8_ENCODING,
        errors=CODEC_ERROR_STRATEGY,
        timeout=60,
        check=False,
        input=None,
    )
    assert completion.returncode == 0
    assert completion.stdout == _CRLF_CHILD_STDOUT_NORMALIZED


def test_run_captured_subprocess_honors_cwd(tmp_path: Path) -> None:
    child_code = "import os, sys; sys.stdout.write(os.getcwd())"
    completion = runner._run_captured_subprocess(
        [sys.executable, "-c", child_code],
        encoding=UTF8_ENCODING,
        errors=CODEC_ERROR_STRATEGY,
        timeout=60,
        check=False,
        cwd=str(tmp_path),
    )
    assert completion.returncode == 0
    assert Path(completion.stdout).resolve() == tmp_path.resolve()


def test_run_captured_subprocess_timeout_keeps_partial_stdout() -> None:
    child_code = (
        "import sys, time;"
        "sys.stdout.write('partial-before-timeout');"
        "sys.stdout.flush();"
        "time.sleep(30)"
    )
    with pytest.raises(subprocess.TimeoutExpired) as raised:
        runner._run_captured_subprocess(
            [sys.executable, "-c", child_code],
            encoding=UTF8_ENCODING,
            errors=CODEC_ERROR_STRATEGY,
            timeout=1,
            check=False,
            input=None,
        )
    assert raised.value.stdout == "partial-before-timeout"
    assert isinstance(raised.value.stdout, str)


def test_run_captured_subprocess_reads_stdin_stream(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt_body.txt"
    prompt_path.write_text(_STDIN_ECHO_PAYLOAD, encoding=UTF8_ENCODING)
    child_code = "import sys; sys.stdout.write(sys.stdin.read())"
    with prompt_path.open(encoding=UTF8_ENCODING) as prompt_stream:
        completion = runner._run_captured_subprocess(
            [sys.executable, "-c", child_code],
            encoding=UTF8_ENCODING,
            errors=CODEC_ERROR_STRATEGY,
            timeout=60,
            check=False,
            stdin=prompt_stream,
        )
    assert completion.returncode == 0
    assert completion.stdout == _STDIN_ECHO_PAYLOAD


def test_cli_emits_utf8_when_console_encoding_is_legacy(tmp_path: Path) -> None:
    tmp_home = tmp_path / "home"
    claude_directory = tmp_home / CLAUDE_HOME_SUBDIRECTORY
    claude_directory.mkdir(parents=True)
    config_file = claude_directory / CONFIG_FILENAME
    config_file.write_text(
        json.dumps({CONFIG_CHAIN_KEY: [_entry(sys.executable)]}),
        encoding=UTF8_ENCODING,
    )
    runner_script = _SCRIPTS_DIR / "claude_chain_runner.py"
    child_code = 'import sys; sys.stdout.buffer.write("report ✅".encode("utf-8"))'
    legacy_console_encoding = "cp1252"
    child_environment = dict(os.environ)
    child_environment["USERPROFILE"] = str(tmp_home)
    child_environment["HOME"] = str(tmp_home)
    child_environment["PYTHONIOENCODING"] = legacy_console_encoding
    child_environment.pop("PYTHONUTF8", None)
    runner_command = [
        sys.executable,
        str(runner_script),
        CLI_ARGUMENTS_SEPARATOR,
        "-c",
        child_code,
    ]
    completed = subprocess.run(
        runner_command,
        capture_output=True,
        env=child_environment,
        timeout=60,
    )
    assert completed.returncode == 0
    assert b"Traceback" not in completed.stderr
    assert "report ✅" in completed.stdout.decode(UTF8_ENCODING)


_SESSION_ID_FOR_AFFINITY = "11111111-2222-3333-4444-555555555555"
_SESSION_JSON_STDOUT = (
    '{"type":"result","result":"ok","session_id":"'
    + _SESSION_ID_FOR_AFFINITY
    + '"}'
)
_SESSION_MISSING_MESSAGE = "No conversation found with session ID: " + _SESSION_ID_FOR_AFFINITY


def _install_affinity_path(monkeypatch: pytest.MonkeyPatch, affinity_file: Path) -> None:
    monkeypatch.setattr(runner, "session_affinity_path", lambda: affinity_file)


def _install_affinity_map(
    monkeypatch: pytest.MonkeyPatch, affinity_file: Path, pinned_command: str
) -> None:
    affinity_file.write_text(
        json.dumps({"sessions": {_SESSION_ID_FOR_AFFINITY: pinned_command}}),
        encoding=UTF8_ENCODING,
    )
    _install_affinity_path(monkeypatch, affinity_file)


def test_session_affinity_path_points_at_home_map() -> None:
    affinity_path = runner.session_affinity_path()
    assert affinity_path.name == SESSION_AFFINITY_FILENAME
    assert CLAUDE_HOME_SUBDIRECTORY in affinity_path.parts


def test_successful_json_stdout_records_session_affinity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude-ev"), _entry("claude")])
    affinity_file = tmp_path / "affinity.json"
    _install_affinity_path(monkeypatch, affinity_file)
    _install(
        monkeypatch,
        config_file,
        {
            "claude-ev": _completed("claude-ev", 0, stdout=_SESSION_JSON_STDOUT),
            "claude": _completed("claude", 0, stdout="unused"),
        },
        weekly_usage_reporter=_usage_reporter_from_remaining(
            {
                "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
                "claude": _LOW_WEEKLY_REMAINING_PERCENT,
            }
        ),
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.returncode == 0
    assert chain_result.served_command == "claude-ev"
    stored = json.loads(affinity_file.read_text(encoding=UTF8_ENCODING))
    assert stored["sessions"][_SESSION_ID_FOR_AFFINITY] == "claude-ev"


def test_resume_pins_affinity_binary_before_higher_ranked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install_affinity_map(monkeypatch, tmp_path / "affinity.json", "claude")
    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 0, stdout="from-pinned"),
            "claude-ev": _completed("claude-ev", 0, stdout="from-ranked"),
        },
        weekly_usage_reporter=_usage_reporter_from_remaining(
            {
                "claude": _LOW_WEEKLY_REMAINING_PERCENT,
                "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
            }
        ),
    )
    resume_arguments = ["-p", "--resume", _SESSION_ID_FOR_AFFINITY, "hello"]
    chain_result = runner.run_claude(resume_arguments, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert chain_result.stdout == "from-pinned"
    assert recorder.invocations[0][0] == "claude"


def test_resume_without_affinity_keeps_ranked_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    affinity_file = tmp_path / "affinity.json"
    _install_affinity_path(monkeypatch, affinity_file)
    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 0, stdout="from-claude"),
            "claude-ev": _completed("claude-ev", 0, stdout="from-ev"),
        },
        weekly_usage_reporter=_usage_reporter_from_remaining(
            {
                "claude": _LOW_WEEKLY_REMAINING_PERCENT,
                "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
            }
        ),
    )
    resume_arguments = ["-p", "--resume", _SESSION_ID_FOR_AFFINITY, "hello"]
    chain_result = runner.run_claude(resume_arguments, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"
    assert recorder.invocations[0][0] == "claude-ev"


def test_resume_session_missing_falls_over_to_next_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install_affinity_map(monkeypatch, tmp_path / "affinity.json", "claude")
    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed(
                "claude", 1, stderr=_SESSION_MISSING_MESSAGE
            ),
            "claude-ev": _completed("claude-ev", 0, stdout=_SESSION_JSON_STDOUT),
        },
        weekly_usage_reporter=_usage_reporter_from_remaining(
            {
                "claude": _HIGH_WEEKLY_REMAINING_PERCENT,
                "claude-ev": _LOW_WEEKLY_REMAINING_PERCENT,
            }
        ),
    )
    resume_arguments = ["-p", "--resume", _SESSION_ID_FOR_AFFINITY]
    chain_result = runner.run_claude(resume_arguments, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"
    assert chain_result.returncode == 0
    assert [each_attempt.status for each_attempt in chain_result.attempts] == [
        "session_missing",
        "served",
    ]
    assert recorder.invocations[0][0] == "claude"
    assert recorder.invocations[1][0] == "claude-ev"


def test_non_resume_session_missing_does_not_fall_over(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 1, stderr=_SESSION_MISSING_MESSAGE),
            "claude-ev": _completed("claude-ev", 0, stdout="should-not-run"),
        },
        weekly_usage_reporter=_usage_reporter_from_remaining(
            {
                "claude": _HIGH_WEEKLY_REMAINING_PERCENT,
                "claude-ev": _LOW_WEEKLY_REMAINING_PERCENT,
            }
        ),
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert chain_result.returncode == 1
    assert len(recorder.invocations) == 1


def test_resume_session_id_equals_form(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install_affinity_map(monkeypatch, tmp_path / "affinity.json", "claude")
    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 0, stdout="pinned"),
            "claude-ev": _completed("claude-ev", 0, stdout="ranked"),
        },
        weekly_usage_reporter=_usage_reporter_from_remaining(
            {
                "claude": _LOW_WEEKLY_REMAINING_PERCENT,
                "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
            }
        ),
    )
    resume_arguments = ["-p", f"--resume={_SESSION_ID_FOR_AFFINITY}"]
    chain_result = runner.run_claude(resume_arguments, timeout_seconds=5)
    assert chain_result.served_command == "claude"
    assert recorder.invocations[0][0] == "claude"


def test_session_id_from_ndjson_stdout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    affinity_file = tmp_path / "affinity.json"
    _install_affinity_path(monkeypatch, affinity_file)
    ndjson_stdout = (
        '{"type":"assistant","message":{"content":[]}}\n'
        + _SESSION_JSON_STDOUT
        + "\n"
    )
    _install(
        monkeypatch,
        config_file,
        {"claude": _completed("claude", 0, stdout=ndjson_stdout)},
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.returncode == 0
    stored = json.loads(affinity_file.read_text(encoding=UTF8_ENCODING))
    assert stored["sessions"][_SESSION_ID_FOR_AFFINITY] == "claude"


def test_stale_affinity_command_missing_from_chain_keeps_ranked_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install_affinity_map(monkeypatch, tmp_path / "affinity.json", "missing-binary")
    recorder = _install(
        monkeypatch,
        config_file,
        {
            "claude": _completed("claude", 0, stdout="from-claude"),
            "claude-ev": _completed("claude-ev", 0, stdout="from-ev"),
        },
        weekly_usage_reporter=_usage_reporter_from_remaining(
            {
                "claude": _LOW_WEEKLY_REMAINING_PERCENT,
                "claude-ev": _HIGH_WEEKLY_REMAINING_PERCENT,
            }
        ),
    )
    resume_arguments = ["-p", "--resume", _SESSION_ID_FOR_AFFINITY]
    chain_result = runner.run_claude(resume_arguments, timeout_seconds=5)
    assert chain_result.served_command == "claude-ev"
    assert recorder.invocations[0][0] == "claude-ev"

