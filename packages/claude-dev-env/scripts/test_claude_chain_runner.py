"""Behavioral tests for the claude fallback-chain runner."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import claude_chain_runner as runner  # noqa: E402
from dev_env_scripts_constants.claude_chain_constants import (  # noqa: E402
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

_A_SIGNATURE = ALL_USAGE_LIMIT_SIGNATURES[0]
_PROMPT_ARGUMENTS = ["-p", "hello"]


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


class _Recorder:
    def __init__(self, behavior_by_command):
        self.behavior_by_command = behavior_by_command
        self.invocations = []
        self.timeouts = []

    def __call__(self, invocation, **keyword_arguments):
        self.invocations.append(invocation)
        self.timeouts.append(keyword_arguments.get("timeout"))
        behavior = self.behavior_by_command[invocation[0]]
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior


def _install(monkeypatch, config_file, behavior_by_command):
    recorder = _Recorder(behavior_by_command)
    monkeypatch.setattr(runner, "chain_config_path", lambda: config_file)
    monkeypatch.setattr(runner, "chain_subprocess_runner", recorder)
    return recorder


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


def test_missing_primary_binary_does_not_fall_over(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = _write_chain_config(tmp_path, [_entry("claude"), _entry("claude-ev")])
    _install(
        monkeypatch,
        config_file,
        {
            "claude": FileNotFoundError(),
            "claude-ev": _completed("claude-ev", 0),
        },
    )
    chain_result = runner.run_claude(_PROMPT_ARGUMENTS, timeout_seconds=5)
    assert chain_result.served_command is None
    assert len(chain_result.attempts) == 1
    assert chain_result.attempts[0].status == ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND


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
