"""Tests for the usage-pause window resolver."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
RESOLVER_PATH = SCRIPTS_DIRECTORY / "resolve_usage_window.py"
INGRESS_TOKEN_FILE_ENV_VAR = "CLAUDE_SESSION_INGRESS_TOKEN_FILE"


def load_resolver_module() -> ModuleType:
    if str(SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIRECTORY))
    spec = importlib.util.spec_from_file_location("resolve_usage_window", RESOLVER_PATH)
    assert spec is not None
    assert spec.loader is not None
    resolver_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = resolver_module
    spec.loader.exec_module(resolver_module)
    return resolver_module


def local_now() -> datetime:
    return datetime(2026, 7, 8, 9, 0, 0).astimezone()


class TestParseManualOverride:
    def should_parse_clock_time_with_pm_meridiem_to_same_day(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = resolver.parse_manual_override("10:20pm", now)
        assert reset_at.hour == 22
        assert reset_at.minute == 20
        assert reset_at.date() == now.date()

    def should_roll_clock_time_to_next_day_when_already_past(self) -> None:
        resolver = load_resolver_module()
        now = datetime(2026, 7, 8, 23, 0, 0).astimezone()
        reset_at = resolver.parse_manual_override("10:20pm", now)
        assert reset_at.date() == (now + timedelta(days=1)).date()
        assert reset_at.hour == 22

    def should_parse_hour_only_clock_time_with_meridiem(self) -> None:
        resolver = load_resolver_module()
        reset_at = resolver.parse_manual_override("10pm", local_now())
        assert reset_at.hour == 22
        assert reset_at.minute == 0

    def should_parse_twenty_four_hour_clock_time(self) -> None:
        resolver = load_resolver_module()
        reset_at = resolver.parse_manual_override("22:15", local_now())
        assert reset_at.hour == 22
        assert reset_at.minute == 15

    def should_parse_am_clock_time(self) -> None:
        resolver = load_resolver_module()
        now = datetime(2026, 7, 8, 6, 0, 0).astimezone()
        reset_at = resolver.parse_manual_override("9:05am", now)
        assert reset_at.hour == 9
        assert reset_at.minute == 5

    def should_parse_minutes_duration(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = resolver.parse_manual_override("74m", now)
        assert reset_at == now + timedelta(minutes=74)

    def should_parse_bare_digits_as_minutes(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = resolver.parse_manual_override("45", now)
        assert reset_at == now + timedelta(minutes=45)

    def should_parse_hours_and_minutes_duration(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = resolver.parse_manual_override("1h30m", now)
        assert reset_at == now + timedelta(minutes=90)

    def should_parse_hours_only_duration(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = resolver.parse_manual_override("2h", now)
        assert reset_at == now + timedelta(hours=2)

    def should_reject_unparseable_override(self) -> None:
        resolver = load_resolver_module()
        with pytest.raises(ValueError):
            resolver.parse_manual_override("soon", local_now())

    def should_reject_meridiem_hour_out_of_range(self) -> None:
        resolver = load_resolver_module()
        with pytest.raises(ValueError):
            resolver.parse_manual_override("13pm", local_now())


class TestPlanWakeupStages:
    def should_split_long_wait_into_capped_stages_with_short_tail(self) -> None:
        resolver = load_resolver_module()
        stages = resolver.plan_wakeup_stages(4440)
        assert stages == [3480, 960, 120]

    def should_land_total_sleep_past_the_reset_by_the_tail_buffer(self) -> None:
        resolver = load_resolver_module()
        stages = resolver.plan_wakeup_stages(4440)
        assert sum(stages) == 4440 + 120

    def should_emit_single_stage_for_a_wait_shorter_than_tail_plus_minimum(
        self,
    ) -> None:
        resolver = load_resolver_module()
        assert resolver.plan_wakeup_stages(30) == [150]

    def should_fold_a_sub_minimum_leftover_into_the_tail(self) -> None:
        resolver = load_resolver_module()
        stages = resolver.plan_wakeup_stages(3510)
        assert stages == [3480, 150]

    def should_keep_every_stage_within_cap_and_minimum_across_a_sweep(self) -> None:
        resolver = load_resolver_module()
        for seconds_until_reset in range(0, 36000, 137):
            stages = resolver.plan_wakeup_stages(seconds_until_reset)
            assert stages, f"no stages for {seconds_until_reset}"
            assert sum(stages) >= seconds_until_reset
            for each_stage in stages:
                assert 60 <= each_stage <= 3480


class TestReadOauthAccessToken:
    def write_credentials(self, target: Path, expires_at_milliseconds: int) -> None:
        payload = {
            "claudeAiOauth": {
                "accessToken": "token-value",
                "refreshToken": "refresh-value",
                "expiresAt": expires_at_milliseconds,
            }
        }
        target.write_text(json.dumps(payload), encoding="utf-8")

    def should_return_token_when_not_expired(self, tmp_path: Path) -> None:
        resolver = load_resolver_module()
        now = local_now()
        credentials_path = tmp_path / ".credentials.json"
        future_milliseconds = int((now + timedelta(hours=1)).timestamp() * 1000)
        self.write_credentials(credentials_path, future_milliseconds)
        assert resolver.read_oauth_access_token(credentials_path, now) == "token-value"

    def should_return_none_when_token_expired(self, tmp_path: Path) -> None:
        resolver = load_resolver_module()
        now = local_now()
        credentials_path = tmp_path / ".credentials.json"
        past_milliseconds = int((now - timedelta(hours=1)).timestamp() * 1000)
        self.write_credentials(credentials_path, past_milliseconds)
        assert resolver.read_oauth_access_token(credentials_path, now) is None

    def should_return_none_when_file_missing(self, tmp_path: Path) -> None:
        resolver = load_resolver_module()
        missing_path = tmp_path / "absent.json"
        assert resolver.read_oauth_access_token(missing_path, local_now()) is None


class TestReadSessionIngressToken:
    def should_return_stripped_token_from_the_named_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        token_file = tmp_path / "ingress-token"
        token_file.write_text("  ingress-token-value\n", encoding="utf-8")
        monkeypatch.setenv(INGRESS_TOKEN_FILE_ENV_VAR, str(token_file))
        assert resolver.read_session_ingress_token() == "ingress-token-value"

    def should_return_none_when_env_var_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        monkeypatch.delenv(INGRESS_TOKEN_FILE_ENV_VAR, raising=False)
        assert resolver.read_session_ingress_token() is None

    def should_return_none_when_named_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        monkeypatch.setenv(INGRESS_TOKEN_FILE_ENV_VAR, str(tmp_path / "absent-token"))
        assert resolver.read_session_ingress_token() is None

    def should_return_none_when_file_is_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        token_file = tmp_path / "ingress-token"
        token_file.write_text("   \n", encoding="utf-8")
        monkeypatch.setenv(INGRESS_TOKEN_FILE_ENV_VAR, str(token_file))
        assert resolver.read_session_ingress_token() is None


class TestResolveAccessToken:
    def write_valid_credentials(self, target: Path, now: datetime) -> None:
        future_milliseconds = int((now + timedelta(hours=1)).timestamp() * 1000)
        payload = {
            "claudeAiOauth": {
                "accessToken": "credential-token",
                "refreshToken": "refresh-value",
                "expiresAt": future_milliseconds,
            }
        }
        target.write_text(json.dumps(payload), encoding="utf-8")

    def should_use_ingress_token_when_credential_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        missing_credentials = tmp_path / "absent.json"
        token_file = tmp_path / "ingress-token"
        token_file.write_text("ingress-token-value", encoding="utf-8")
        monkeypatch.setenv(INGRESS_TOKEN_FILE_ENV_VAR, str(token_file))
        chosen_token = resolver.resolve_access_token(missing_credentials, local_now())
        assert chosen_token == "ingress-token-value"

    def should_prefer_credential_token_over_ingress_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        now = local_now()
        credentials_path = tmp_path / ".credentials.json"
        self.write_valid_credentials(credentials_path, now)
        token_file = tmp_path / "ingress-token"
        token_file.write_text("ingress-token-value", encoding="utf-8")
        monkeypatch.setenv(INGRESS_TOKEN_FILE_ENV_VAR, str(token_file))
        chosen_token = resolver.resolve_access_token(credentials_path, now)
        assert chosen_token == "credential-token"

    def should_return_none_when_ingress_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        missing_credentials = tmp_path / "absent.json"
        monkeypatch.setenv(INGRESS_TOKEN_FILE_ENV_VAR, str(tmp_path / "absent-token"))
        assert resolver.resolve_access_token(missing_credentials, local_now()) is None

    def should_return_none_when_ingress_file_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        missing_credentials = tmp_path / "absent.json"
        token_file = tmp_path / "ingress-token"
        token_file.write_text("   \n", encoding="utf-8")
        monkeypatch.setenv(INGRESS_TOKEN_FILE_ENV_VAR, str(token_file))
        assert resolver.resolve_access_token(missing_credentials, local_now()) is None

    def should_return_none_when_env_unset_and_no_credential_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolver = load_resolver_module()
        monkeypatch.delenv(INGRESS_TOKEN_FILE_ENV_VAR, raising=False)
        missing_credentials = tmp_path / "absent.json"
        assert resolver.resolve_access_token(missing_credentials, local_now()) is None


class TestExtractUsageWindows:
    def should_extract_session_and_weekly_buckets(self) -> None:
        resolver = load_resolver_module()
        payload = {
            "five_hour": {"utilization": 42, "resets_at": "2026-07-08T22:00:00+00:00"},
            "seven_day": {"utilization": 63, "resets_at": "2026-07-12T00:00:00+00:00"},
        }
        windows = resolver.extract_usage_windows(payload)
        assert isinstance(windows, resolver.UsageWindows)
        assert windows.session_utilization == 42.0
        assert windows.weekly_utilization == 63.0
        assert windows.session_resets_at is not None
        assert windows.weekly_resets_at is not None

    def should_accept_epoch_seconds_resets_at(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        epoch_seconds = int((now + timedelta(hours=2)).timestamp())
        payload = {"five_hour": {"utilization": 10, "resets_at": epoch_seconds}}
        windows = resolver.extract_usage_windows(payload)
        assert windows.session_resets_at is not None
        assert abs((windows.session_resets_at - now).total_seconds() - 7200) < 2

    def should_handle_missing_buckets(self) -> None:
        resolver = load_resolver_module()
        windows = resolver.extract_usage_windows({})
        assert windows.session_utilization is None
        assert windows.session_resets_at is None
        assert windows.weekly_utilization is None
        assert windows.weekly_resets_at is None


class TestBuildPausePlan:
    def should_flag_weekly_near_cap_at_the_threshold(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = now + timedelta(minutes=74)
        resolved_payload = resolver.build_pause_plan(
            "probe", reset_at, now, 50.0, 95.0, None
        )
        assert resolved_payload["weekly_near_cap"] is True

    def should_not_flag_weekly_near_cap_below_the_threshold(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = now + timedelta(minutes=74)
        resolved_payload = resolver.build_pause_plan(
            "probe", reset_at, now, 50.0, 40.0, None
        )
        assert resolved_payload["weekly_near_cap"] is False

    def should_carry_stage_plan_and_reset_time(self) -> None:
        resolver = load_resolver_module()
        now = local_now()
        reset_at = now + timedelta(seconds=4440)
        resolved_payload = resolver.build_pause_plan(
            "override", reset_at, now, None, None, None
        )
        assert resolved_payload["source"] == "override"
        assert resolved_payload["seconds_until_reset"] == 4440
        assert resolved_payload["stages_seconds"] == [3480, 960, 120]
        assert resolved_payload["reset_at"] == reset_at.isoformat()


class TestCommandLine:
    def run_resolver(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        child_environment = dict(os.environ)
        child_environment.pop(INGRESS_TOKEN_FILE_ENV_VAR, None)
        return subprocess.run(
            [sys.executable, str(RESOLVER_PATH), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=child_environment,
        )

    def should_resolve_duration_override_end_to_end(self) -> None:
        now = local_now()
        completed = self.run_resolver("--override", "74m", "--now", now.isoformat())
        assert completed.returncode == 0, completed.stderr
        resolved_payload = json.loads(completed.stdout)
        assert resolved_payload["source"] == "override"
        assert resolved_payload["stages_seconds"] == [3480, 960, 120]
        assert resolved_payload["weekly_near_cap"] is False

    def should_resolve_clock_override_end_to_end(self) -> None:
        now = datetime(2026, 7, 8, 21, 0, 0).astimezone()
        completed = self.run_resolver("--override", "10:20pm", "--now", now.isoformat())
        assert completed.returncode == 0, completed.stderr
        resolved_payload = json.loads(completed.stdout)
        assert resolved_payload["seconds_until_reset"] == 4800

    def should_exit_with_probe_unavailable_code_when_credentials_missing(
        self, tmp_path: Path
    ) -> None:
        missing_path = tmp_path / "absent.json"
        completed = self.run_resolver("--credentials-path", str(missing_path))
        assert completed.returncode == 2
        resolved_payload = json.loads(completed.stdout)
        assert "error" in resolved_payload

    def should_reject_invalid_override_with_error_payload(self) -> None:
        completed = self.run_resolver("--override", "soon")
        assert completed.returncode == 2
        resolved_payload = json.loads(completed.stdout)
        assert "error" in resolved_payload

    def should_reject_invalid_now_with_error_payload(self) -> None:
        completed = self.run_resolver("--override", "74m", "--now", "not-a-time")
        assert completed.returncode == 2
        resolved_payload = json.loads(completed.stdout)
        assert "error" in resolved_payload
