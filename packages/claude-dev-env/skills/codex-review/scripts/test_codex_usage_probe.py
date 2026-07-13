"""Tests for the Codex weekly-usage probe CLI.

Fixtures note the binary version they were captured against:
codex-cli 0.144.3 (account/rateLimits/read via ``codex app-server``).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from codex_review_scripts_constants.codex_usage_probe_constants import (
    EXIT_CODE_SUCCESS,
    PERCENT_FULL,
    SOURCE_APP_SERVER_RATE_LIMITS,
    SOURCE_NO_USAGE_SURFACE,
    USAGE_REPORT_KEY_PERCENT_LEFT,
    USAGE_REPORT_KEY_SOURCE,
    USAGE_REPORT_KEY_WINDOW_RESET,
    WEEKLY_USAGE_GATE_THRESHOLD_PERCENT,
    WEEKLY_WINDOW_DURATION_MINUTES,
)

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
PROBE_PATH = SCRIPTS_DIRECTORY / "codex_usage_probe.py"

REAL_APP_SERVER_RATE_LIMITS_REPLY_CODEX_0_144_3 = json.dumps(
    {
        "id": 2,
        "result": {
            "rateLimits": {
                "limitId": "codex",
                "limitName": None,
                "primary": {
                    "usedPercent": 95,
                    "windowDurationMins": WEEKLY_WINDOW_DURATION_MINUTES,
                    "resetsAt": 1784504948,
                },
                "secondary": None,
                "credits": {
                    "hasCredits": False,
                    "unlimited": False,
                    "balance": None,
                },
                "individualLimit": None,
                "planType": "team",
                "rateLimitReachedType": None,
            }
        },
    }
)

DUAL_WINDOW_APP_SERVER_RATE_LIMITS_REPLY = json.dumps(
    {
        "id": 2,
        "result": {
            "rateLimits": {
                "limitId": "codex",
                "primary": {
                    "usedPercent": 40,
                    "windowDurationMins": 300,
                    "resetsAt": 1783958400,
                },
                "secondary": {
                    "usedPercent": 20,
                    "windowDurationMins": WEEKLY_WINDOW_DURATION_MINUTES,
                    "resetsAt": 1784504948,
                },
            }
        },
    }
)

NO_USAGE_SURFACE_LOGIN_STATUS_OUTPUT = "Logged in using ChatGPT\n"

NO_RATE_LIMITS_APP_SERVER_REPLY = json.dumps(
    {
        "id": 2,
        "result": {"rateLimits": {}},
    }
)

JSON_RPC_ERROR_APP_SERVER_REPLY = json.dumps(
    {
        "id": 2,
        "error": {
            "code": -32601,
            "message": "Method not found",
        },
    }
)

TEXT_STATUS_WITH_WEEKLY_LEFT = (
    "Status\n"
    "5-hour limit: 60% left\n"
    "Weekly limit: 42% left (resets 2026-07-19T23:49:08+00:00)\n"
)

TIMEOUT_SECONDS = 30
TIMEOUT_COMMAND = "codex"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("codex_usage_probe", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    probe_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = probe_module
    spec.loader.exec_module(probe_module)
    return probe_module


def _app_server_lines_from_rate_limits_payload(payload_line: str) -> list[str]:
    return [
        json.dumps(
            {
                "id": 1,
                "result": {
                    "userAgent": "codex-usage-probe/0.144.3",
                    "platformOs": "windows",
                },
            }
        ),
        payload_line,
    ]


def _assert_main_yields_null_skip_report(
    probe: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = probe.main()
    assert exit_code == EXIT_CODE_SUCCESS
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload[USAGE_REPORT_KEY_PERCENT_LEFT] is None
    assert payload[USAGE_REPORT_KEY_SOURCE] == SOURCE_NO_USAGE_SURFACE
    assert USAGE_REPORT_KEY_WINDOW_RESET in payload


class TestParseRateLimitsMessage:
    def should_compute_percent_left_from_weekly_primary_window(
        self,
    ) -> None:
        probe = load_probe_module()
        usage_report = probe.parse_rate_limits_message(
            REAL_APP_SERVER_RATE_LIMITS_REPLY_CODEX_0_144_3
        )
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] == 5
        assert usage_report[USAGE_REPORT_KEY_WINDOW_RESET] is not None
        assert usage_report[USAGE_REPORT_KEY_SOURCE] == SOURCE_APP_SERVER_RATE_LIMITS

    def should_prefer_secondary_weekly_window_over_primary_session(
        self,
    ) -> None:
        probe = load_probe_module()
        usage_report = probe.parse_rate_limits_message(
            DUAL_WINDOW_APP_SERVER_RATE_LIMITS_REPLY
        )
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] == 80
        assert usage_report[USAGE_REPORT_KEY_WINDOW_RESET] is not None

    def should_return_null_percent_when_rate_limits_empty(self) -> None:
        probe = load_probe_module()
        usage_report = probe.parse_rate_limits_message(
            NO_RATE_LIMITS_APP_SERVER_REPLY
        )
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] is None
        assert usage_report[USAGE_REPORT_KEY_WINDOW_RESET] is None
        assert usage_report[USAGE_REPORT_KEY_SOURCE] == SOURCE_NO_USAGE_SURFACE

    def should_return_null_percent_when_json_rpc_error_payload(self) -> None:
        probe = load_probe_module()
        usage_report = probe.parse_rate_limits_message(JSON_RPC_ERROR_APP_SERVER_REPLY)
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] is None
        assert usage_report[USAGE_REPORT_KEY_WINDOW_RESET] is None
        assert usage_report[USAGE_REPORT_KEY_SOURCE] == SOURCE_NO_USAGE_SURFACE


class TestParseTextStatus:
    def should_parse_weekly_percent_left_from_status_text(self) -> None:
        probe = load_probe_module()
        usage_report = probe.parse_text_usage_status(TEXT_STATUS_WITH_WEEKLY_LEFT)
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] == 42.0
        assert usage_report[USAGE_REPORT_KEY_WINDOW_RESET] is not None

    def should_yield_null_for_login_status_without_usage(self) -> None:
        probe = load_probe_module()
        usage_report = probe.parse_text_usage_status(
            NO_USAGE_SURFACE_LOGIN_STATUS_OUTPUT
        )
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] is None
        assert usage_report[USAGE_REPORT_KEY_SOURCE] == SOURCE_NO_USAGE_SURFACE


class TestProbeWeeklyUsage:
    def should_probe_through_swappable_app_server_exchange(self) -> None:
        probe = load_probe_module()
        all_server_lines = _app_server_lines_from_rate_limits_payload(
            REAL_APP_SERVER_RATE_LIMITS_REPLY_CODEX_0_144_3
        )

        def fake_exchange(all_request_messages: list[dict[str, object]]) -> list[str]:
            assert len(all_request_messages) >= 2
            return all_server_lines

        usage_report = probe.probe_weekly_usage(
            exchange_app_server_messages=fake_exchange
        )
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] == 5
        assert usage_report[USAGE_REPORT_KEY_SOURCE] == SOURCE_APP_SERVER_RATE_LIMITS

    def should_yield_null_when_exchange_returns_no_usage_payload(self) -> None:
        probe = load_probe_module()

        def empty_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            return [
                json.dumps({"id": 1, "result": {}}),
                NO_RATE_LIMITS_APP_SERVER_REPLY,
            ]

        usage_report = probe.probe_weekly_usage(
            exchange_app_server_messages=empty_exchange
        )
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] is None
        assert usage_report[USAGE_REPORT_KEY_SOURCE] == SOURCE_NO_USAGE_SURFACE

    def should_yield_null_when_exchange_returns_json_rpc_error(self) -> None:
        probe = load_probe_module()

        def error_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            return _app_server_lines_from_rate_limits_payload(
                JSON_RPC_ERROR_APP_SERVER_REPLY
            )

        usage_report = probe.probe_weekly_usage(
            exchange_app_server_messages=error_exchange
        )
        assert usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] is None
        assert usage_report[USAGE_REPORT_KEY_SOURCE] == SOURCE_NO_USAGE_SURFACE


class TestGateThresholdHelper:
    def should_export_threshold_constant_of_ten(self) -> None:
        assert WEEKLY_USAGE_GATE_THRESHOLD_PERCENT == 10

    def should_skip_review_when_percent_is_null(self) -> None:
        probe = load_probe_module()
        assert probe.is_codex_review_required(None) is False

    def should_skip_review_when_percent_at_or_below_threshold(self) -> None:
        probe = load_probe_module()
        assert (
            probe.is_codex_review_required(float(WEEKLY_USAGE_GATE_THRESHOLD_PERCENT))
            is False
        )
        assert probe.is_codex_review_required(5.0) is False

    def should_require_review_when_percent_above_threshold(self) -> None:
        probe = load_probe_module()
        assert probe.is_codex_review_required(10.1) is True
        assert probe.is_codex_review_required(float(PERCENT_FULL)) is True


class TestMainExitCodes:
    def should_exit_zero_with_json_even_when_usage_is_null(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        probe = load_probe_module()

        def empty_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            return [NO_RATE_LIMITS_APP_SERVER_REPLY]

        monkeypatch.setattr(
            probe,
            "_exchange_app_server_messages_via_subprocess",
            empty_exchange,
        )
        _assert_main_yields_null_skip_report(probe, capsys)

    def should_exit_zero_with_null_report_when_binary_missing(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        probe = load_probe_module()

        def missing_binary_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            raise FileNotFoundError("codex binary not found on PATH")

        monkeypatch.setattr(
            probe,
            "_exchange_app_server_messages_via_subprocess",
            missing_binary_exchange,
        )
        _assert_main_yields_null_skip_report(probe, capsys)

    def should_exit_zero_with_null_report_when_subprocess_times_out(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        probe = load_probe_module()

        def timeout_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            raise subprocess.TimeoutExpired(
                cmd=TIMEOUT_COMMAND,
                timeout=TIMEOUT_SECONDS,
            )

        monkeypatch.setattr(
            probe,
            "_exchange_app_server_messages_via_subprocess",
            timeout_exchange,
        )
        _assert_main_yields_null_skip_report(probe, capsys)

    def should_exit_zero_with_null_report_when_os_error(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        probe = load_probe_module()

        def os_error_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            raise OSError("permission denied launching codex")

        monkeypatch.setattr(
            probe,
            "_exchange_app_server_messages_via_subprocess",
            os_error_exchange,
        )
        _assert_main_yields_null_skip_report(probe, capsys)

    def should_exit_zero_with_null_report_when_subprocess_error(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        probe = load_probe_module()

        def subprocess_error_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            raise subprocess.SubprocessError("codex app-server failed")

        monkeypatch.setattr(
            probe,
            "_exchange_app_server_messages_via_subprocess",
            subprocess_error_exchange,
        )
        _assert_main_yields_null_skip_report(probe, capsys)

    def should_exit_zero_with_null_report_when_json_rpc_error_payload(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        probe = load_probe_module()

        def error_payload_exchange(
            all_request_messages: list[dict[str, object]],
        ) -> list[str]:
            del all_request_messages
            return _app_server_lines_from_rate_limits_payload(
                JSON_RPC_ERROR_APP_SERVER_REPLY
            )

        monkeypatch.setattr(
            probe,
            "_exchange_app_server_messages_via_subprocess",
            error_payload_exchange,
        )
        _assert_main_yields_null_skip_report(probe, capsys)
