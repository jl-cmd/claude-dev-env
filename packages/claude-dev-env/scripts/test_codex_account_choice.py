"""Tests for the picker that names which Codex account a runner job uses."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import codex_account_choice as choice
from codex_account_meters import CodexAccountMeters, CodexMeterUnreadError, UsageWindow

NOW = datetime(2026, 9, 23, 17, 0, tzinfo=timezone.utc)


def reading(
    name: str,
    *,
    weekly_used: float,
    short_used: float = 0.0,
    weekly_resets_in: timedelta = timedelta(days=3),
) -> choice.AccountReading:
    return choice.AccountReading(
        name=name,
        codex_home=Path("/profiles") / name,
        meters=CodexAccountMeters(
            all_windows=(
                UsageWindow(300, short_used, NOW + timedelta(hours=2)),
                UsageWindow(10080, weekly_used, NOW + weekly_resets_in),
            )
        ),
    )


def unread(name: str) -> choice.AccountReading:
    return choice.AccountReading(name, Path("/profiles") / name, None, "not signed in")


class TestChooseCodexAccount:
    def should_take_the_first_account_in_order_with_room(self) -> None:
        decision = choice.choose_codex_account(
            [reading("codex-1", weekly_used=50.0), reading("codex-2", weekly_used=0.0)]
        )
        assert (decision.tier, decision.reading.name) == ("normal", "codex-1")
        assert decision.stop_below_percent is None

    def should_pass_over_an_account_at_the_ten_percent_bar(self) -> None:
        decision = choice.choose_codex_account(
            [reading("codex-1", weekly_used=90.0), reading("codex-2", weekly_used=60.0)]
        )
        assert (decision.tier, decision.reading.name) == ("normal", "codex-2")

    def should_measure_room_by_the_tightest_window(self) -> None:
        decision = choice.choose_codex_account(
            [
                reading("codex-1", weekly_used=10.0, short_used=95.0),
                reading("codex-2", weekly_used=70.0),
            ]
        )
        assert decision.reading.name == "codex-2"

    def should_skip_an_unread_account(self) -> None:
        decision = choice.choose_codex_account(
            [unread("codex-1"), reading("codex-2", weekly_used=20.0)]
        )
        assert (decision.tier, decision.reading.name) == ("normal", "codex-2")

    def should_fall_back_to_luna_on_the_roomiest_account_under_the_bar(self) -> None:
        decision = choice.choose_codex_account(
            [
                reading("codex-1", weekly_used=97.0),
                reading("codex-2", weekly_used=92.0),
                reading("codex-3", weekly_used=100.0),
            ]
        )
        assert (decision.tier, decision.reading.name) == ("luna", "codex-2")
        assert decision.stop_below_percent == 1.0

    def should_keep_luna_off_an_account_under_twenty_percent_of_its_five_hour_window(
        self,
    ) -> None:
        decision = choice.choose_codex_account(
            [
                reading("codex-1", weekly_used=92.0, short_used=85.0),
                reading("codex-2", weekly_used=97.0, short_used=80.0),
            ]
        )
        assert (decision.tier, decision.reading.name) == ("luna", "codex-2")

    def should_run_luna_on_an_account_with_no_five_hour_window(self) -> None:
        weekly_only = choice.AccountReading(
            "codex-3",
            Path("/profiles/codex-3"),
            CodexAccountMeters((UsageWindow(10080, 95.0, NOW + timedelta(days=1)),)),
        )
        decision = choice.choose_codex_account(
            [reading("codex-1", weekly_used=92.0, short_used=90.0), weekly_only]
        )
        assert (decision.tier, decision.reading.name) == ("luna", "codex-3")

    def should_wait_on_the_account_that_resets_first_when_none_passes_one_percent(
        self,
    ) -> None:
        decision = choice.choose_codex_account(
            [
                reading(
                    "codex-1", weekly_used=99.5, weekly_resets_in=timedelta(days=2)
                ),
                reading(
                    "codex-2", weekly_used=100.0, weekly_resets_in=timedelta(hours=6)
                ),
            ]
        )
        assert decision.tier == "wait"
        assert decision.reading.name == "codex-2"
        assert (NOW + timedelta(hours=6)).isoformat() in decision.reason

    def should_wait_when_no_meter_reads(self) -> None:
        decision = choice.choose_codex_account([unread("codex-1"), unread("codex-2")])
        assert (decision.tier, decision.reading) == ("wait", None)


class TestDecisionPayload:
    def should_name_no_account_or_home_on_wait(self) -> None:
        all_readings = [reading("codex-1", weekly_used=100.0)]
        payload = choice.decision_payload(
            choice.choose_codex_account(all_readings), all_readings
        )
        assert (payload["tier"], payload["account"], payload["codex_home"]) == (
            "wait",
            None,
            None,
        )

    def should_report_every_account_and_the_chosen_home(self) -> None:
        all_readings = [unread("codex-1"), reading("codex-2", weekly_used=25.0)]
        payload = choice.decision_payload(
            choice.choose_codex_account(all_readings), all_readings
        )
        assert payload["codex_home"] == str(Path("/profiles") / "codex-2")
        assert payload["percent_left"] == 75.0
        assert [each["name"] for each in payload["accounts"]] == ["codex-1", "codex-2"]
        assert payload["accounts"][0]["unread"] == "not signed in"
        json.dumps(payload)


class TestReadAccount:
    def should_call_an_account_without_a_sign_in_unread(self, tmp_path: Path) -> None:
        def never_called(codex_home: Path) -> CodexAccountMeters:
            raise AssertionError("no sign-in, no read")

        account_reading = choice.read_account("codex-1", tmp_path, never_called)
        assert (account_reading.meters, account_reading.unread_reason) == (None, "not signed in")

    def should_read_under_the_accounts_own_home(self, tmp_path: Path) -> None:
        (tmp_path / "codex-2").mkdir()
        (tmp_path / "codex-2" / "auth.json").write_text("{}")
        all_homes: list[Path] = []

        def fake_reader(codex_home: Path) -> CodexAccountMeters:
            all_homes.append(codex_home)
            return CodexAccountMeters((UsageWindow(10080, 40.0, None),))

        account_reading = choice.read_account("codex-2", tmp_path, fake_reader)
        assert all_homes == [tmp_path / "codex-2"]
        assert account_reading.meters.percent_left == 60.0

    def should_keep_the_unread_reason(self, tmp_path: Path) -> None:
        (tmp_path / "codex-1").mkdir()
        (tmp_path / "codex-1" / "auth.json").write_text("{}")

        def failing_reader(codex_home: Path) -> CodexAccountMeters:
            raise CodexMeterUnreadError("codex app-server sent no rate-limit reply")

        account_reading = choice.read_account("codex-1", tmp_path, failing_reader)
        assert account_reading.unread_reason == "codex app-server sent no rate-limit reply"


class TestCheck:
    @pytest.mark.parametrize(
        ("weekly_used", "exit_code"), [(98.0, 0), (99.0, 3), (100.0, 3)]
    )
    def should_answer_room_only_above_the_floor(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        weekly_used: float,
        exit_code: int,
    ) -> None:
        (tmp_path / "codex-3").mkdir()
        (tmp_path / "codex-3" / "auth.json").write_text("{}")
        monkeypatch.setattr(
            choice,
            "_meter_reader",
            lambda codex_path: (
                lambda codex_home: CodexAccountMeters(
                    (UsageWindow(10080, weekly_used, None),)
                )
            ),
        )
        assert (
            choice.main(["--profiles-root", str(tmp_path), "check", "codex-3"])
            == exit_code
        )

    def should_answer_no_room_for_an_unread_account(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(choice, "_meter_reader", lambda codex_path: None)
        assert choice.main(["--profiles-root", str(tmp_path), "check", "codex-4"]) == 3


class TestSync:
    @pytest.mark.skipif(
        os.name == "nt", reason="junction creation needs a Windows shell"
    )
    def should_link_the_shared_setup_and_keep_each_sign_in(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main_home = tmp_path / "main"
        (main_home / "rules").mkdir(parents=True)
        (main_home / "config.toml").write_text("model = 'x'")
        (main_home / "auth.json").write_text("{}")
        (main_home / "sessions").mkdir()
        profiles_root = tmp_path / "profiles"

        assert (
            choice.main(
                [
                    "--profiles-root",
                    str(profiles_root),
                    "sync",
                    "--main-home",
                    str(main_home),
                ]
            )
            == 0
        )

        report = json.loads(capsys.readouterr().out)
        assert list(report) == ["codex-1", "codex-2", "codex-3", "codex-4"]
        each_home = profiles_root / "codex-3"
        assert os.readlink(each_home / "rules") == str(main_home / "rules")
        assert os.readlink(each_home / "config.toml") == str(main_home / "config.toml")
        assert not (each_home / "auth.json").exists()
        assert not (each_home / "sessions").exists()


class TestSmallHelpers:
    @pytest.mark.parametrize(
        ("entry_name", "is_local"),
        [("auth.json", True), ("sessions", True), ("state_5.sqlite", True), ("config.toml", False), ("plugins", False)],
    )
    def should_keep_every_entry_outside_the_shared_set_per_account(
        self, entry_name: str, is_local: bool
    ) -> None:
        assert choice.is_account_local_codex_entry(entry_name) is is_local

    def should_take_the_profiles_root_from_the_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CODEX_PROFILES_ROOT", str(tmp_path))
        assert choice.default_profiles_root() == tmp_path

    def should_default_the_profiles_root_under_the_user_home(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CODEX_PROFILES_ROOT", raising=False)
        assert choice.default_profiles_root() == Path.home() / ".codex-profiles"

    def should_list_each_window_in_a_read_accounts_payload(self) -> None:
        payload = choice.reading_payload(reading("codex-1", weekly_used=40.0, short_used=5.0))
        assert payload["percent_left"] == 60.0
        assert [each["minutes"] for each in payload["windows"]] == [300, 10080]
