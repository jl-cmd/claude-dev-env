"""Behavioral tests for the grok worker preflight soft gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import grok_worker_preflight as preflight  # noqa: E402
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    AGENTS_SUBDIRECTORY,
    ALL_AGENT_FILENAMES_BY_ROLE,
    ALL_AUTH_FAILURE_SIGNATURES,
    ALL_USAGE_EXHAUSTION_SIGNATURES,
    AUTH_LEADER_SOCKET_FILENAME,
    CLI_PING_FLAG,
    CLI_ROLE_FLAG,
    CLI_RUN_STATE_DIR_FLAG,
    DEFAULT_ROLE,
    EXIT_FALLTHROUGH,
    EXIT_USABLE,
    GROK_BINARY_NAME,
    LEADER_SOCKET_FLAG,
    MANIFEST_FILENAME,
    MODELS_SUBCOMMAND,
    PING_CACHE_CHECKED_AT_KEY,
    PING_CACHE_FILENAME,
    PING_CACHE_IS_OK_KEY,
    PING_LEADER_SOCKET_FILENAME,
    PING_MAX_TURNS,
    PING_PROMPT,
    PING_TTL_SECONDS,
    REASON_CLAUDE_DEV_ENV_CONFIG_MISSING,
    REASON_GROK_AUTH_FAILED,
    REASON_GROK_BINARY_MISSING,
    REASON_GROK_USAGE_EXHAUSTED,
    ROLE_BUGTEAM,
    SINGLE_TURN_FLAG,
    STDOUT_FALLTHROUGH_TEMPLATE,
    STDOUT_OK_LINE,
    UTF8_ENCODING,
)


def _completed(
    command: list[str],
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=command, returncode=returncode, stdout=stdout, stderr=stderr
    )


class _Recorder:
    def __init__(self, all_completions: list[subprocess.CompletedProcess[str]]) -> None:
        self.all_completions = list(all_completions)
        self.invocations: list[list[str]] = []

    def __call__(
        self,
        invocation: list[str],
        **_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        self.invocations.append(list(invocation))
        if not self.all_completions:
            raise AssertionError(f"unexpected invocation: {invocation}")
        return self.all_completions.pop(0)


def _write_install_layout(claude_home: Path, *, role: str = ROLE_BUGTEAM) -> None:
    claude_home.mkdir(parents=True, exist_ok=True)
    (claude_home / MANIFEST_FILENAME).write_text("{}", encoding=UTF8_ENCODING)
    agents_directory = claude_home / AGENTS_SUBDIRECTORY
    agents_directory.mkdir(parents=True, exist_ok=True)
    for each_filename in ALL_AGENT_FILENAMES_BY_ROLE[role]:
        (agents_directory / each_filename).write_text(
            f"# {each_filename}\n", encoding=UTF8_ENCODING
        )


def _install_ok_static_seams(
    monkeypatch: pytest.MonkeyPatch,
    claude_home: Path,
    recorder: _Recorder,
) -> None:
    _write_install_layout(claude_home)
    monkeypatch.setattr(preflight, "claude_config_home", lambda: claude_home)
    monkeypatch.setattr(
        preflight, "preflight_which", lambda name: f"/fake/bin/{name}"
    )
    monkeypatch.setattr(preflight, "preflight_subprocess_runner", recorder)


def test_binary_missing_falls_through_with_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    _write_install_layout(claude_home)
    monkeypatch.setattr(preflight, "claude_config_home", lambda: claude_home)
    monkeypatch.setattr(preflight, "preflight_which", lambda _name: None)
    monkeypatch.setattr(
        preflight,
        "preflight_subprocess_runner",
        _Recorder([_completed([GROK_BINARY_NAME], 0)]),
    )

    exit_code = preflight.main(
        [CLI_RUN_STATE_DIR_FLAG, str(run_state_directory)]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_FALLTHROUGH
    assert captured.out.strip() == STDOUT_FALLTHROUGH_TEMPLATE.format(
        reason=REASON_GROK_BINARY_MISSING
    )


def test_auth_failed_falls_through_with_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [
            _completed(
                [GROK_BINARY_NAME, MODELS_SUBCOMMAND],
                1,
                stderr=ALL_AUTH_FAILURE_SIGNATURES[0],
            )
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)

    exit_code = preflight.main(
        [CLI_RUN_STATE_DIR_FLAG, str(run_state_directory)]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_FALLTHROUGH
    assert captured.out.strip() == STDOUT_FALLTHROUGH_TEMPLATE.format(
        reason=REASON_GROK_AUTH_FAILED
    )
    assert recorder.invocations[0][0] == GROK_BINARY_NAME
    assert MODELS_SUBCOMMAND in recorder.invocations[0]
    assert LEADER_SOCKET_FLAG in recorder.invocations[0]
    leader_socket_path = Path(
        recorder.invocations[0][
            recorder.invocations[0].index(LEADER_SOCKET_FLAG) + 1
        ]
    )
    assert leader_socket_path.name == AUTH_LEADER_SOCKET_FILENAME
    assert leader_socket_path.parent == run_state_directory


def test_config_missing_manifest_falls_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [_completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in")]
    )
    monkeypatch.setattr(preflight, "claude_config_home", lambda: claude_home)
    monkeypatch.setattr(
        preflight, "preflight_which", lambda name: f"/fake/bin/{name}"
    )
    monkeypatch.setattr(preflight, "preflight_subprocess_runner", recorder)

    exit_code = preflight.main(
        [CLI_RUN_STATE_DIR_FLAG, str(run_state_directory)]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_FALLTHROUGH
    assert captured.out.strip() == STDOUT_FALLTHROUGH_TEMPLATE.format(
        reason=REASON_CLAUDE_DEV_ENV_CONFIG_MISSING
    )


def test_config_missing_role_agent_falls_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    (claude_home / MANIFEST_FILENAME).write_text("{}", encoding=UTF8_ENCODING)
    agents_directory = claude_home / AGENTS_SUBDIRECTORY
    agents_directory.mkdir()
    (agents_directory / "code-quality-agent.md").write_text(
        "# present\n", encoding=UTF8_ENCODING
    )
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [_completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in")]
    )
    monkeypatch.setattr(preflight, "claude_config_home", lambda: claude_home)
    monkeypatch.setattr(
        preflight, "preflight_which", lambda name: f"/fake/bin/{name}"
    )
    monkeypatch.setattr(preflight, "preflight_subprocess_runner", recorder)

    exit_code = preflight.main(
        [
            CLI_ROLE_FLAG,
            ROLE_BUGTEAM,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_FALLTHROUGH
    assert captured.out.strip() == STDOUT_FALLTHROUGH_TEMPLATE.format(
        reason=REASON_CLAUDE_DEV_ENV_CONFIG_MISSING
    )


def test_ok_path_without_ping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [_completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in")]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)

    exit_code = preflight.main(
        [CLI_RUN_STATE_DIR_FLAG, str(run_state_directory)]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_USABLE
    assert captured.out.strip() == STDOUT_OK_LINE
    assert len(recorder.invocations) == 1
    assert MODELS_SUBCOMMAND in recorder.invocations[0]


def test_ping_cache_miss_invokes_live_call_and_writes_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    fixed_now = 1_700_000_000.0
    recorder = _Recorder(
        [
            _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
            _completed([GROK_BINARY_NAME, SINGLE_TURN_FLAG], 0, stdout="ok"),
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: fixed_now)

    exit_code = preflight.main(
        [
            CLI_PING_FLAG,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_USABLE
    assert captured.out.strip() == STDOUT_OK_LINE
    assert len(recorder.invocations) == 2
    ping_invocation = recorder.invocations[1]
    assert SINGLE_TURN_FLAG in ping_invocation
    assert PING_PROMPT in ping_invocation
    assert PING_MAX_TURNS in ping_invocation
    assert LEADER_SOCKET_FLAG in ping_invocation
    ping_socket = Path(
        ping_invocation[ping_invocation.index(LEADER_SOCKET_FLAG) + 1]
    )
    assert ping_socket.name == PING_LEADER_SOCKET_FILENAME
    cache_path = run_state_directory / PING_CACHE_FILENAME
    all_cache_payload = json.loads(cache_path.read_text(encoding=UTF8_ENCODING))
    assert all_cache_payload[PING_CACHE_IS_OK_KEY] is True
    assert all_cache_payload[PING_CACHE_CHECKED_AT_KEY] == fixed_now


def test_ping_cache_hit_skips_live_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    fixed_now = 1_700_000_100.0
    cache_path = run_state_directory / PING_CACHE_FILENAME
    cache_path.write_text(
        json.dumps(
            {
                PING_CACHE_CHECKED_AT_KEY: fixed_now - 10.0,
                PING_CACHE_IS_OK_KEY: True,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    recorder = _Recorder(
        [_completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in")]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: fixed_now)

    exit_code = preflight.main(
        [
            CLI_PING_FLAG,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_USABLE
    assert captured.out.strip() == STDOUT_OK_LINE
    assert len(recorder.invocations) == 1
    assert MODELS_SUBCOMMAND in recorder.invocations[0]


def test_ping_cache_ttl_expired_reinvokes_live_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    fixed_now = 1_700_000_000.0 + PING_TTL_SECONDS + 1.0
    cache_path = run_state_directory / PING_CACHE_FILENAME
    cache_path.write_text(
        json.dumps(
            {
                PING_CACHE_CHECKED_AT_KEY: 1_700_000_000.0,
                PING_CACHE_IS_OK_KEY: True,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    recorder = _Recorder(
        [
            _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
            _completed([GROK_BINARY_NAME, SINGLE_TURN_FLAG], 0, stdout="ok"),
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: fixed_now)

    exit_code = preflight.main(
        [
            CLI_PING_FLAG,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_USABLE
    assert captured.out.strip() == STDOUT_OK_LINE
    assert len(recorder.invocations) == 2


def test_auth_failure_invalidates_ping_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    cache_path = run_state_directory / PING_CACHE_FILENAME
    cache_path.write_text(
        json.dumps(
            {
                PING_CACHE_CHECKED_AT_KEY: 1_700_000_000.0,
                PING_CACHE_IS_OK_KEY: True,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    recorder = _Recorder(
        [
            _completed(
                [GROK_BINARY_NAME, MODELS_SUBCOMMAND],
                1,
                stderr="not logged in",
            )
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)

    exit_code = preflight.main(
        [
            CLI_PING_FLAG,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_FALLTHROUGH
    assert captured.out.strip() == STDOUT_FALLTHROUGH_TEMPLATE.format(
        reason=REASON_GROK_AUTH_FAILED
    )
    assert not cache_path.exists()


def test_ping_usage_exhaustion_is_distinct_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [
            _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
            _completed(
                [GROK_BINARY_NAME, SINGLE_TURN_FLAG],
                1,
                stderr=ALL_USAGE_EXHAUSTION_SIGNATURES[0],
            ),
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: 1_700_000_000.0)

    exit_code = preflight.main(
        [
            CLI_PING_FLAG,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_FALLTHROUGH
    assert captured.out.strip() == STDOUT_FALLTHROUGH_TEMPLATE.format(
        reason=REASON_GROK_USAGE_EXHAUSTED
    )
    assert not (run_state_directory / PING_CACHE_FILENAME).exists()


def test_ping_auth_failure_is_auth_reason_not_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [
            _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
            _completed(
                [GROK_BINARY_NAME, SINGLE_TURN_FLAG],
                1,
                stderr=ALL_AUTH_FAILURE_SIGNATURES[0],
            ),
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: 1_700_000_000.0)

    exit_code = preflight.main(
        [
            CLI_PING_FLAG,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_FALLTHROUGH
    assert captured.out.strip() == STDOUT_FALLTHROUGH_TEMPLATE.format(
        reason=REASON_GROK_AUTH_FAILED
    )


def test_reason_strings_are_pinned_to_constants() -> None:
    assert REASON_GROK_BINARY_MISSING == "grok_binary_missing"
    assert REASON_GROK_AUTH_FAILED == "grok_auth_failed"
    assert REASON_CLAUDE_DEV_ENV_CONFIG_MISSING == "claude_dev_env_config_missing"
    assert REASON_GROK_USAGE_EXHAUSTED == "grok_usage_exhausted"
    assert STDOUT_OK_LINE == "grok_preflight: ok"
    assert "reason=" in STDOUT_FALLTHROUGH_TEMPLATE
    assert DEFAULT_ROLE == ROLE_BUGTEAM


def test_claude_config_home_points_at_user_claude_home() -> None:
    config_home = preflight.claude_config_home()
    assert config_home.name == ".claude"


def test_run_preflight_binary_missing_returns_fallthrough(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    _write_install_layout(claude_home)
    monkeypatch.setattr(preflight, "claude_config_home", lambda: claude_home)
    monkeypatch.setattr(preflight, "preflight_which", lambda _name: None)

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=False,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is False
    assert outcome.reason == REASON_GROK_BINARY_MISSING


def test_run_preflight_auth_failure_invalidates_cache_and_returns_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    cache_path = run_state_directory / PING_CACHE_FILENAME
    cache_path.write_text(
        json.dumps(
            {
                PING_CACHE_CHECKED_AT_KEY: 1_700_000_000.0,
                PING_CACHE_IS_OK_KEY: True,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    recorder = _Recorder(
        [
            _completed(
                [GROK_BINARY_NAME, MODELS_SUBCOMMAND],
                1,
                stderr=ALL_AUTH_FAILURE_SIGNATURES[0],
            )
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=False,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is False
    assert outcome.reason == REASON_GROK_AUTH_FAILED
    assert not cache_path.exists()
    assert MODELS_SUBCOMMAND in recorder.invocations[0]
    leader_socket_path = Path(
        recorder.invocations[0][
            recorder.invocations[0].index(LEADER_SOCKET_FLAG) + 1
        ]
    )
    assert leader_socket_path.name == AUTH_LEADER_SOCKET_FILENAME


def test_run_preflight_config_missing_returns_fallthrough(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    claude_home.mkdir()
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [_completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in")]
    )
    monkeypatch.setattr(preflight, "claude_config_home", lambda: claude_home)
    monkeypatch.setattr(
        preflight, "preflight_which", lambda name: f"/fake/bin/{name}"
    )
    monkeypatch.setattr(preflight, "preflight_subprocess_runner", recorder)

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=False,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is False
    assert outcome.reason == REASON_CLAUDE_DEV_ENV_CONFIG_MISSING


def test_run_preflight_ok_without_ping_returns_usable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [_completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in")]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=False,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is True
    assert outcome.reason is None
    assert len(recorder.invocations) == 1
    assert MODELS_SUBCOMMAND in recorder.invocations[0]


def test_run_preflight_ping_cache_miss_writes_cache_and_returns_usable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    fixed_now = 1_700_000_000.0
    recorder = _Recorder(
        [
            _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
            _completed([GROK_BINARY_NAME, SINGLE_TURN_FLAG], 0, stdout="ok"),
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: fixed_now)

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=True,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is True
    assert outcome.reason is None
    assert len(recorder.invocations) == 2
    ping_invocation = recorder.invocations[1]
    assert SINGLE_TURN_FLAG in ping_invocation
    assert PING_PROMPT in ping_invocation
    ping_socket = Path(
        ping_invocation[ping_invocation.index(LEADER_SOCKET_FLAG) + 1]
    )
    assert ping_socket.name == PING_LEADER_SOCKET_FILENAME
    cache_path = run_state_directory / PING_CACHE_FILENAME
    all_cache_payload = json.loads(cache_path.read_text(encoding=UTF8_ENCODING))
    assert all_cache_payload[PING_CACHE_IS_OK_KEY] is True
    assert all_cache_payload[PING_CACHE_CHECKED_AT_KEY] == fixed_now


def test_run_preflight_ping_cache_hit_skips_live_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    fixed_now = 1_700_000_100.0
    cache_path = run_state_directory / PING_CACHE_FILENAME
    cache_path.write_text(
        json.dumps(
            {
                PING_CACHE_CHECKED_AT_KEY: fixed_now - 10.0,
                PING_CACHE_IS_OK_KEY: True,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    recorder = _Recorder(
        [_completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in")]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: fixed_now)

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=True,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is True
    assert outcome.reason is None
    assert len(recorder.invocations) == 1
    assert MODELS_SUBCOMMAND in recorder.invocations[0]


def test_run_preflight_ping_usage_exhaustion_returns_distinct_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    recorder = _Recorder(
        [
            _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
            _completed(
                [GROK_BINARY_NAME, SINGLE_TURN_FLAG],
                1,
                stderr=ALL_USAGE_EXHAUSTION_SIGNATURES[0],
            ),
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(preflight, "preflight_time", lambda: 1_700_000_000.0)

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=True,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is False
    assert outcome.reason == REASON_GROK_USAGE_EXHAUSTED
    assert not (run_state_directory / PING_CACHE_FILENAME).exists()


def test_run_preflight_ping_auth_failure_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    cache_path = run_state_directory / PING_CACHE_FILENAME
    cache_path.write_text(
        json.dumps(
            {
                PING_CACHE_CHECKED_AT_KEY: 1_700_000_000.0,
                PING_CACHE_IS_OK_KEY: True,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    recorder = _Recorder(
        [
            _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
            _completed(
                [GROK_BINARY_NAME, SINGLE_TURN_FLAG],
                1,
                stderr=ALL_AUTH_FAILURE_SIGNATURES[0],
            ),
        ]
    )
    _install_ok_static_seams(monkeypatch, claude_home, recorder)
    monkeypatch.setattr(
        preflight, "preflight_time", lambda: 1_700_000_000.0 + PING_TTL_SECONDS + 1.0
    )

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=True,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is False
    assert outcome.reason == REASON_GROK_AUTH_FAILED
    assert not cache_path.exists()


def test_run_preflight_ping_missing_binary_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_home = tmp_path / "claude"
    run_state_directory = tmp_path / "run"
    run_state_directory.mkdir()
    cache_path = run_state_directory / PING_CACHE_FILENAME
    cache_path.write_text(
        json.dumps(
            {
                PING_CACHE_CHECKED_AT_KEY: 1_700_000_000.0,
                PING_CACHE_IS_OK_KEY: True,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    all_completions = [
        _completed([GROK_BINARY_NAME, MODELS_SUBCOMMAND], 0, stdout="logged in"),
    ]

    def _raise_on_ping(
        invocation: list[str], **_keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        if SINGLE_TURN_FLAG in invocation:
            raise FileNotFoundError(GROK_BINARY_NAME)
        if not all_completions:
            raise AssertionError(f"unexpected invocation: {invocation}")
        return all_completions.pop(0)

    _write_install_layout(claude_home)
    monkeypatch.setattr(preflight, "claude_config_home", lambda: claude_home)
    monkeypatch.setattr(
        preflight, "preflight_which", lambda name: f"/fake/bin/{name}"
    )
    monkeypatch.setattr(preflight, "preflight_subprocess_runner", _raise_on_ping)
    monkeypatch.setattr(
        preflight, "preflight_time", lambda: 1_700_000_000.0 + PING_TTL_SECONDS + 1.0
    )

    outcome = preflight.run_preflight(
        role=ROLE_BUGTEAM,
        should_ping=True,
        run_state_directory=run_state_directory,
    )

    assert outcome.is_usable is False
    assert outcome.reason == REASON_GROK_AUTH_FAILED
    assert not cache_path.exists()
