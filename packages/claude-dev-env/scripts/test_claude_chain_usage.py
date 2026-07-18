"""Behavioral tests for the claude chain weekly-usage report tool."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import claude_chain_runner as chain_runner  # noqa: E402
import claude_chain_usage as usage  # noqa: E402
from dev_env_scripts_constants.claude_chain_constants import (  # noqa: E402
    CHAIN_CONFIG_ERROR_EXIT_CODE,
    CONFIG_CHAIN_KEY,
    CONFIG_COMMAND_KEY,
    CONFIG_CREDENTIALS_PATH_KEY,
    CONFIG_EXTRA_ARGS_KEY,
    CONFIG_FILENAME,
    UTF8_ENCODING,
)
from dev_env_scripts_constants.claude_chain_usage_constants import (  # noqa: E402
    CLI_CONFIG_PATH_FLAG,
    FULL_WEEKLY_PERCENT,
    JSON_ACCOUNTS_KEY,
    JSON_COMMAND_KEY,
    JSON_ERROR_KEY,
    JSON_WEEKLY_REMAINING_PERCENT_KEY,
    RESOLVE_USAGE_WINDOW_MODULE_NAME,
)

PLACEHOLDER_CREDENTIALS_PRIMARY = "/path/to/account-primary/.credentials.json"
PLACEHOLDER_CREDENTIALS_SECONDARY = "/path/to/account-secondary/.credentials.json"
PLACEHOLDER_CREDENTIALS_TERTIARY = "/path/to/account-tertiary/.credentials.json"


def _entry(
    command: str,
    *,
    extra_args: list[str] | None = None,
    credentials_path: str | None = None,
) -> dict[str, object]:
    chain_entry: dict[str, object] = {
        CONFIG_COMMAND_KEY: command,
        CONFIG_EXTRA_ARGS_KEY: extra_args if extra_args is not None else [],
    }
    if credentials_path is not None:
        chain_entry[CONFIG_CREDENTIALS_PATH_KEY] = credentials_path
    return chain_entry


def _write_chain_config(
    tmp_path: Path, all_chain_entries: list[dict[str, object]]
) -> Path:
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text(
        json.dumps({CONFIG_CHAIN_KEY: all_chain_entries}), encoding=UTF8_ENCODING
    )
    return config_file


def _probe_from_utilization_by_path(
    utilization_by_path: dict[str, float | Exception],
) -> usage.WeeklyUtilizationProbe:
    def active_probe(credentials_path: Path) -> float:
        path_key = credentials_path.as_posix()
        probe_outcome = utilization_by_path[path_key]
        if isinstance(probe_outcome, Exception):
            raise probe_outcome
        return probe_outcome

    return active_probe


def test_remaining_percent_is_full_scale_minus_utilization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [
            _entry("claude", credentials_path=PLACEHOLDER_CREDENTIALS_PRIMARY),
            _entry("claude-ev", credentials_path=PLACEHOLDER_CREDENTIALS_SECONDARY),
        ],
    )
    monkeypatch.setattr(
        usage,
        "weekly_utilization_probe",
        _probe_from_utilization_by_path(
            {
                PLACEHOLDER_CREDENTIALS_PRIMARY: 42.0,
                PLACEHOLDER_CREDENTIALS_SECONDARY: 9.0,
            }
        ),
    )
    all_reports = usage.report_chain_weekly_usage(config_path=config_file)
    assert [each_report.command for each_report in all_reports] == [
        "claude",
        "claude-ev",
    ]
    assert all_reports[0].weekly_remaining_percent == pytest.approx(
        FULL_WEEKLY_PERCENT - 42.0
    )
    assert all_reports[1].weekly_remaining_percent == pytest.approx(
        FULL_WEEKLY_PERCENT - 9.0
    )
    assert all_reports[0].error is None
    assert all_reports[1].error is None


def test_rank_orders_by_remaining_desc_preserves_ties_and_puts_nulls_last() -> None:
    all_reports = [
        usage.AccountUsageReport(command="first", weekly_remaining_percent=40.0),
        usage.AccountUsageReport(command="second", weekly_remaining_percent=70.0),
        usage.AccountUsageReport(
            command="third", weekly_remaining_percent=None, error="probe failed"
        ),
        usage.AccountUsageReport(command="fourth", weekly_remaining_percent=70.0),
        usage.AccountUsageReport(
            command="fifth", weekly_remaining_percent=None, error="no token"
        ),
        usage.AccountUsageReport(command="sixth", weekly_remaining_percent=10.0),
    ]
    ranked_reports = usage.rank_accounts_by_weekly_remaining(all_reports)
    assert [each_report.command for each_report in ranked_reports] == [
        "second",
        "fourth",
        "first",
        "sixth",
        "third",
        "fifth",
    ]


def test_probe_failure_yields_null_remaining_and_error_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [
            _entry("claude", credentials_path=PLACEHOLDER_CREDENTIALS_PRIMARY),
            _entry("claude-ev", credentials_path=PLACEHOLDER_CREDENTIALS_SECONDARY),
        ],
    )
    monkeypatch.setattr(
        usage,
        "weekly_utilization_probe",
        _probe_from_utilization_by_path(
            {
                PLACEHOLDER_CREDENTIALS_PRIMARY: usage.WeeklyUtilizationProbeError(
                    "token expired"
                ),
                PLACEHOLDER_CREDENTIALS_SECONDARY: 25.0,
            }
        ),
    )
    all_reports = usage.report_chain_weekly_usage(config_path=config_file)
    assert all_reports[0].weekly_remaining_percent is None
    assert all_reports[0].error == "token expired"
    assert all_reports[1].weekly_remaining_percent == pytest.approx(
        FULL_WEEKLY_PERCENT - 25.0
    )
    assert all_reports[1].error is None


def test_missing_config_raises_chain_configuration_error(tmp_path: Path) -> None:
    missing_config = tmp_path / "absent-chain.json"
    with pytest.raises(chain_runner.ChainConfigurationError):
        usage.report_chain_weekly_usage(config_path=missing_config)


def test_empty_config_raises_chain_configuration_error(tmp_path: Path) -> None:
    config_file = _write_chain_config(tmp_path, [])
    with pytest.raises(chain_runner.ChainConfigurationError):
        usage.report_chain_weekly_usage(config_path=config_file)


def test_entry_without_credentials_path_uses_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default_path = Path("/path/to/default/.credentials.json")
    monkeypatch.setattr(usage, "_default_credentials_path", lambda: default_path)
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    probed_paths: list[Path] = []

    def active_probe(credentials_path: Path) -> float:
        probed_paths.append(credentials_path)
        return 10.0

    monkeypatch.setattr(usage, "weekly_utilization_probe", active_probe)
    all_reports = usage.report_chain_weekly_usage(config_path=config_file)
    assert probed_paths == [default_path]
    assert all_reports[0].weekly_remaining_percent == pytest.approx(
        FULL_WEEKLY_PERCENT - 10.0
    )


def test_default_credentials_resolution_failure_yields_null_remaining(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_probe_error() -> Path:
        raise usage.WeeklyUtilizationProbeError("probe module not found")

    monkeypatch.setattr(usage, "_default_credentials_path", raise_probe_error)
    config_file = _write_chain_config(tmp_path, [_entry("claude")])
    all_reports = usage.report_chain_weekly_usage(config_path=config_file)
    assert all_reports[0].weekly_remaining_percent is None
    assert all_reports[0].error == "probe module not found"


def test_entry_credentials_path_is_passed_to_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [_entry("claude-ev", credentials_path=PLACEHOLDER_CREDENTIALS_TERTIARY)],
    )
    probed_paths: list[Path] = []

    def active_probe(credentials_path: Path) -> float:
        probed_paths.append(credentials_path)
        return 0.0

    monkeypatch.setattr(usage, "weekly_utilization_probe", active_probe)
    usage.report_chain_weekly_usage(config_path=config_file)
    assert probed_paths == [Path(PLACEHOLDER_CREDENTIALS_TERTIARY)]


def test_entry_credentials_path_expands_user_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tilde_credentials_path = "~/.claude-accounts/secondary/.credentials.json"
    config_file = _write_chain_config(
        tmp_path,
        [_entry("claude-ev", credentials_path=tilde_credentials_path)],
    )
    probed_paths: list[Path] = []

    def active_probe(credentials_path: Path) -> float:
        probed_paths.append(credentials_path)
        return 0.0

    monkeypatch.setattr(usage, "weekly_utilization_probe", active_probe)
    usage.report_chain_weekly_usage(config_path=config_file)
    assert probed_paths == [Path(tilde_credentials_path).expanduser()]


def test_load_chain_carries_optional_credentials_path(tmp_path: Path) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [
            _entry("claude"),
            _entry("claude-ev", credentials_path=PLACEHOLDER_CREDENTIALS_SECONDARY),
        ],
    )
    all_entries = chain_runner.load_chain(config_file)
    assert all_entries[0].credentials_path is None
    assert all_entries[1].credentials_path == PLACEHOLDER_CREDENTIALS_SECONDARY


def test_invalid_credentials_path_type_raises(tmp_path: Path) -> None:
    config_file = tmp_path / CONFIG_FILENAME
    config_file.write_text(
        json.dumps(
            {
                CONFIG_CHAIN_KEY: [
                    {
                        CONFIG_COMMAND_KEY: "claude",
                        CONFIG_EXTRA_ARGS_KEY: [],
                        CONFIG_CREDENTIALS_PATH_KEY: 12,
                    }
                ]
            }
        ),
        encoding=UTF8_ENCODING,
    )
    with pytest.raises(chain_runner.ChainConfigurationError):
        chain_runner.load_chain(config_file)


def test_reports_to_json_payload_matches_cli_contract() -> None:
    all_reports = [
        usage.AccountUsageReport(command="claude", weekly_remaining_percent=58.0),
        usage.AccountUsageReport(
            command="claude-ev",
            weekly_remaining_percent=None,
            error="probe failed",
        ),
    ]
    payload = usage.reports_to_json_payload(all_reports)
    assert payload == {
        JSON_ACCOUNTS_KEY: [
            {
                JSON_COMMAND_KEY: "claude",
                JSON_WEEKLY_REMAINING_PERCENT_KEY: 58.0,
            },
            {
                JSON_COMMAND_KEY: "claude-ev",
                JSON_WEEKLY_REMAINING_PERCENT_KEY: None,
                JSON_ERROR_KEY: "probe failed",
            },
        ]
    }


def test_cli_writes_json_accounts_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [
            _entry("claude", credentials_path=PLACEHOLDER_CREDENTIALS_PRIMARY),
            _entry("claude-ev", credentials_path=PLACEHOLDER_CREDENTIALS_SECONDARY),
        ],
    )
    monkeypatch.setattr(
        usage,
        "weekly_utilization_probe",
        _probe_from_utilization_by_path(
            {
                PLACEHOLDER_CREDENTIALS_PRIMARY: 42.0,
                PLACEHOLDER_CREDENTIALS_SECONDARY: usage.WeeklyUtilizationProbeError(
                    "no token"
                ),
            }
        ),
    )
    exit_code = usage.main([CLI_CONFIG_PATH_FLAG, str(config_file)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload == {
        JSON_ACCOUNTS_KEY: [
            {
                JSON_COMMAND_KEY: "claude",
                JSON_WEEKLY_REMAINING_PERCENT_KEY: FULL_WEEKLY_PERCENT - 42.0,
            },
            {
                JSON_COMMAND_KEY: "claude-ev",
                JSON_WEEKLY_REMAINING_PERCENT_KEY: None,
                JSON_ERROR_KEY: "no token",
            },
        ]
    }


def test_cli_missing_config_prints_stderr_and_returns_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_config = tmp_path / "absent-chain.json"
    exit_code = usage.main([CLI_CONFIG_PATH_FLAG, str(missing_config)])
    captured = capsys.readouterr()
    assert exit_code == CHAIN_CONFIG_ERROR_EXIT_CODE
    assert captured.out == ""
    assert "not found" in captured.err.lower() or "claude chain" in captured.err.lower()


def test_weekly_remaining_from_utilization_uses_full_scale() -> None:
    assert usage.weekly_remaining_from_utilization(9.0) == pytest.approx(91.0)
    assert usage.weekly_remaining_from_utilization(0.0) == pytest.approx(
        FULL_WEEKLY_PERCENT
    )
    assert usage.weekly_remaining_from_utilization(100.0) == pytest.approx(0.0)


def test_probe_weekly_utilization_reuses_resolver_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeWindows:
        weekly_utilization = 37.5

    class _FakeResolver:
        def read_oauth_access_token(self, credentials_path: Path, now: object) -> str:
            assert credentials_path == Path(PLACEHOLDER_CREDENTIALS_PRIMARY)
            return "token-value"

        def resolve_access_token(self, credentials_path: Path, now: object) -> str:
            raise AssertionError("probe must not fall back to session ingress")

        def _fetch_usage_payload(self, access_token: str) -> dict[str, object]:
            assert access_token == "token-value"
            return {"seven_day": {"utilization": 37.5}}

        def extract_usage_windows(
            self, usage_payload: dict[str, object]
        ) -> _FakeWindows:
            assert usage_payload == {"seven_day": {"utilization": 37.5}}
            return _FakeWindows()

    monkeypatch.setattr(
        usage, "_load_resolve_usage_window_module", lambda: _FakeResolver()
    )
    weekly_utilization = usage._probe_weekly_utilization(
        Path(PLACEHOLDER_CREDENTIALS_PRIMARY)
    )
    assert weekly_utilization == pytest.approx(37.5)


def test_probe_weekly_utilization_raises_when_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResolver:
        def read_oauth_access_token(
            self, credentials_path: Path, now: object
        ) -> None:
            return None

        def resolve_access_token(self, credentials_path: Path, now: object) -> str:
            return "ingress-token-must-not-be-used"

        def _fetch_usage_payload(self, access_token: str) -> dict[str, object]:
            raise AssertionError("must not probe with an ingress fallback token")

    monkeypatch.setattr(
        usage, "_load_resolve_usage_window_module", lambda: _FakeResolver()
    )
    with pytest.raises(usage.WeeklyUtilizationProbeError):
        usage._probe_weekly_utilization(Path(PLACEHOLDER_CREDENTIALS_PRIMARY))


def test_probe_ignores_ingress_when_credential_token_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [_entry("claude-ev", credentials_path=PLACEHOLDER_CREDENTIALS_SECONDARY)],
    )

    class _FakeResolver:
        def read_oauth_access_token(
            self, credentials_path: Path, now: object
        ) -> None:
            return None

        def resolve_access_token(self, credentials_path: Path, now: object) -> str:
            return "ingress-token-must-not-be-used"

        def _fetch_usage_payload(self, access_token: str) -> dict[str, object]:
            raise AssertionError("must not probe with an ingress fallback token")

    monkeypatch.setattr(
        usage, "_load_resolve_usage_window_module", lambda: _FakeResolver()
    )
    monkeypatch.setattr(usage, "weekly_utilization_probe", usage._probe_weekly_utilization)
    all_reports = usage.report_chain_weekly_usage(config_path=config_file)
    assert all_reports[0].weekly_remaining_percent is None
    assert all_reports[0].error is not None
    assert "bearer token" in all_reports[0].error.lower()


def test_load_failure_yields_per_account_error_and_cli_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_file = _write_chain_config(
        tmp_path,
        [
            _entry("claude", credentials_path=PLACEHOLDER_CREDENTIALS_PRIMARY),
            _entry("claude-ev", credentials_path=PLACEHOLDER_CREDENTIALS_SECONDARY),
        ],
    )

    def active_probe(credentials_path: Path) -> float:
        path_key = credentials_path.as_posix()
        if path_key == PLACEHOLDER_CREDENTIALS_PRIMARY:
            raise ImportError("usage probe module failed to import")
        return 25.0

    monkeypatch.setattr(usage, "weekly_utilization_probe", active_probe)
    exit_code = usage.main([CLI_CONFIG_PATH_FLAG, str(config_file)])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload[JSON_ACCOUNTS_KEY][0][JSON_WEEKLY_REMAINING_PERCENT_KEY] is None
    assert "failed to import" in payload[JSON_ACCOUNTS_KEY][0][JSON_ERROR_KEY]
    assert payload[JSON_ACCOUNTS_KEY][1][JSON_WEEKLY_REMAINING_PERCENT_KEY] == pytest.approx(
        FULL_WEEKLY_PERCENT - 25.0
    )


def test_failed_exec_module_does_not_poison_sys_modules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if RESOLVE_USAGE_WINDOW_MODULE_NAME in sys.modules:
        del sys.modules[RESOLVE_USAGE_WINDOW_MODULE_NAME]
    (tmp_path / "resolve_usage_window.py").write_text(
        "raise ImportError('intentional load failure')\n", encoding="utf-8"
    )
    monkeypatch.setattr(usage, "_usage_pause_scripts_directory", lambda: tmp_path)
    with pytest.raises(ImportError, match="intentional load failure"):
        usage._load_resolve_usage_window_module()
    assert RESOLVE_USAGE_WINDOW_MODULE_NAME not in sys.modules


def test_load_resolve_usage_window_module_loads_real_probe_api() -> None:
    if RESOLVE_USAGE_WINDOW_MODULE_NAME in sys.modules:
        del sys.modules[RESOLVE_USAGE_WINDOW_MODULE_NAME]
    loaded_module = usage._load_resolve_usage_window_module()
    assert callable(loaded_module.read_oauth_access_token)
    assert callable(loaded_module.resolve_access_token)
    assert callable(loaded_module.extract_usage_windows)
    assert callable(loaded_module._fetch_usage_payload)
    assert sys.modules[RESOLVE_USAGE_WINDOW_MODULE_NAME] is loaded_module


def test_load_resolve_usage_window_module_reuses_cached_module() -> None:
    first_load = usage._load_resolve_usage_window_module()
    second_load = usage._load_resolve_usage_window_module()
    assert first_load is second_load


def test_usage_module_imports_without_preloading_runner() -> None:
    scripts_directory = str(_SCRIPTS_DIR)
    import_probe = (
        "import sys; "
        f"sys.path.insert(0, {scripts_directory!r}); "
        "import claude_chain_usage; "
        "assert callable(claude_chain_usage.report_chain_weekly_usage); "
        "assert callable(claude_chain_usage.rank_accounts_by_weekly_remaining)"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-E", "-c", import_probe],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
