"""Tests for the picker that names which Claude account a runner job uses."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import claude_account_choice as choice
from claude_chain_usage import AccountUsageMeters, WeeklyUtilizationProbeError

NOW = datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc)


def meters(
    *,
    session_used: float | None,
    weekly_used: float | None,
    weekly_resets_in: timedelta | None,
    session_resets_in: timedelta = timedelta(hours=2),
) -> AccountUsageMeters:
    return AccountUsageMeters(
        session_utilization=session_used,
        session_resets_at=NOW + session_resets_in,
        weekly_utilization=weekly_used,
        weekly_resets_at=None if weekly_resets_in is None else NOW + weekly_resets_in,
    )


class TestChooseAccount:
    def test_should_pick_main_when_week_resets_soon(self) -> None:
        main_meters = meters(
            session_used=10.0, weekly_used=80.0, weekly_resets_in=timedelta(hours=5)
        )
        second_meters = meters(
            session_used=10.0, weekly_used=82.0, weekly_resets_in=timedelta(days=4)
        )
        decision = choice.choose_account(
            main_meters=main_meters, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_MAIN

    def test_should_pick_second_when_main_week_resets_later_than_a_day(self) -> None:
        main_meters = meters(
            session_used=0.0, weekly_used=5.0, weekly_resets_in=timedelta(hours=30)
        )
        second_meters = meters(
            session_used=10.0, weekly_used=40.0, weekly_resets_in=timedelta(days=4)
        )
        decision = choice.choose_account(
            main_meters=main_meters, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_SECOND

    def test_should_keep_main_once_it_nears_its_weekly_ceiling(self) -> None:
        main_meters = meters(
            session_used=0.0, weekly_used=90.0, weekly_resets_in=timedelta(hours=3)
        )
        second_meters = meters(
            session_used=0.0, weekly_used=10.0, weekly_resets_in=timedelta(days=4)
        )
        decision = choice.choose_account(
            main_meters=main_meters, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_SECOND

    def test_should_keep_main_when_its_five_hour_window_is_half_spent(self) -> None:
        main_meters = meters(
            session_used=50.0, weekly_used=20.0, weekly_resets_in=timedelta(hours=3)
        )
        second_meters = meters(
            session_used=0.0, weekly_used=10.0, weekly_resets_in=timedelta(days=4)
        )
        decision = choice.choose_account(
            main_meters=main_meters, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_SECOND

    def test_should_never_pick_main_when_its_meter_is_unread(self) -> None:
        second_meters = meters(
            session_used=95.0, weekly_used=99.0, weekly_resets_in=timedelta(days=4)
        )
        decision = choice.choose_account(
            main_meters=None, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_WAIT

    def test_should_never_pick_main_when_its_reset_time_is_missing(self) -> None:
        main_meters = meters(session_used=0.0, weekly_used=0.0, weekly_resets_in=None)
        second_meters = meters(
            session_used=95.0, weekly_used=99.0, weekly_resets_in=timedelta(days=4)
        )
        decision = choice.choose_account(
            main_meters=main_meters, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_WAIT

    def test_should_pick_second_when_its_meter_is_unread(self) -> None:
        decision = choice.choose_account(main_meters=None, second_meters=None, now=NOW)
        assert decision.account == choice.CHOICE_SECOND
        assert decision.reason == choice.REASON_SECOND_UNREAD

    def test_should_wait_and_name_the_session_reset_when_the_five_hour_window_blocks(
        self,
    ) -> None:
        second_meters = meters(
            session_used=90.0,
            weekly_used=50.0,
            weekly_resets_in=timedelta(days=4),
            session_resets_in=timedelta(hours=1),
        )
        decision = choice.choose_account(
            main_meters=None, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_WAIT
        assert (NOW + timedelta(hours=1)).isoformat() in decision.reason

    def test_should_wait_and_name_the_weekly_reset_when_the_week_blocks(self) -> None:
        second_meters = meters(
            session_used=10.0, weekly_used=95.0, weekly_resets_in=timedelta(days=2)
        )
        decision = choice.choose_account(
            main_meters=None, second_meters=second_meters, now=NOW
        )
        assert decision.account == choice.CHOICE_WAIT
        assert (NOW + timedelta(days=2)).isoformat() in decision.reason


class TestReadAccountMeters:
    def test_should_return_none_when_the_probe_cannot_read_the_account(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def failing_probe(credentials_path: Path) -> AccountUsageMeters:
            raise WeeklyUtilizationProbeError(f"no token in {credentials_path}")

        monkeypatch.setattr(choice, "probe_account_meters", failing_probe)
        assert choice.read_account_meters(tmp_path / ".credentials.json") is None

    def test_should_return_the_probed_meters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probed = meters(
            session_used=1.0, weekly_used=2.0, weekly_resets_in=timedelta(days=1)
        )
        monkeypatch.setattr(choice, "probe_account_meters", lambda credentials_path: probed)
        assert choice.read_account_meters(tmp_path / ".credentials.json") == probed


class TestDecisionPayload:
    def test_should_name_no_config_directory_for_a_wait(self) -> None:
        decision = choice.AccountDecision(account=choice.CHOICE_WAIT, reason="full")
        assert choice.decision_payload(decision, config_directory=None) == {
            "account": "wait",
            "config_dir": None,
            "reason": "full",
        }


class TestMetersPayload:
    def test_should_name_no_meters_for_an_unread_account(self) -> None:
        assert choice.meters_payload(None) is None

    def test_should_carry_each_used_percent_and_reset_time(self) -> None:
        read_meters = meters(
            session_used=12.0,
            weekly_used=34.0,
            weekly_resets_in=timedelta(days=3),
            session_resets_in=timedelta(hours=1),
        )
        assert choice.meters_payload(read_meters) == {
            "session_used_percent": 12.0,
            "session_resets_at": "2026-09-22T22:00:00+00:00",
            "weekly_used_percent": 34.0,
            "weekly_resets_at": "2026-09-25T21:00:00+00:00",
        }

    def test_should_name_no_reset_time_the_meter_left_out(self) -> None:
        read_meters = meters(session_used=1.0, weekly_used=None, weekly_resets_in=None)
        payload = choice.meters_payload(read_meters)
        assert payload is not None
        assert payload["weekly_used_percent"] is None
        assert payload["weekly_resets_at"] is None


class TestMain:
    def test_should_print_the_choice_and_the_config_directory_of_the_chosen_account(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        main_home = tmp_path / "main"
        second_home = tmp_path / "second"
        meters_by_credentials_path = {
            main_home / ".credentials.json": None,
            second_home / ".credentials.json": meters(
                session_used=0.0, weekly_used=10.0, weekly_resets_in=timedelta(days=4)
            ),
        }
        monkeypatch.setattr(
            choice,
            "read_account_meters",
            lambda credentials_path: meters_by_credentials_path[credentials_path],
        )
        exit_code = choice.main(
            [
                "--main-config-dir",
                str(main_home),
                "--second-config-dir",
                str(second_home),
            ]
        )
        printed = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert printed["account"] == choice.CHOICE_SECOND
        assert printed["config_dir"] == str(second_home)
        assert printed["meters"]["main"] is None
        assert printed["meters"]["second"]["weekly_used_percent"] == 10.0

    def test_should_print_no_config_directory_when_the_job_waits(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        blocked_meters = meters(
            session_used=99.0, weekly_used=99.0, weekly_resets_in=timedelta(days=4)
        )
        monkeypatch.setattr(
            choice, "read_account_meters", lambda credentials_path: blocked_meters
        )
        exit_code = choice.main(
            [
                "--main-config-dir",
                str(tmp_path / "main"),
                "--second-config-dir",
                str(tmp_path / "second"),
            ]
        )
        printed = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert printed["account"] == choice.CHOICE_WAIT
        assert printed["config_dir"] is None


def test_should_pick_second_extra_in_order_and_print_every_meter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main_home = tmp_path / "main"
    first_extra = tmp_path / "first"
    second_extra = tmp_path / "next"
    third_extra = tmp_path / "last"
    readings = {
        main_home: None,
        first_extra: meters(
            session_used=90.0, weekly_used=95.0, weekly_resets_in=timedelta(days=4)
        ),
        second_extra: meters(
            session_used=10.0, weekly_used=20.0, weekly_resets_in=timedelta(days=4)
        ),
        third_extra: meters(
            session_used=30.0, weekly_used=40.0, weekly_resets_in=timedelta(days=4)
        ),
    }
    monkeypatch.setattr(
        choice, "read_account_meters", lambda path: readings[path.parent]
    )

    assert choice.main(
        [
            "--main-config-dir",
            str(main_home),
            "--second-config-dir",
            str(first_extra),
            "--extra-config-dir",
            str(second_extra),
            "--extra-config-dir",
            str(third_extra),
        ]
    ) == 0
    printed = json.loads(capsys.readouterr().out)

    assert printed["account"] == "extra_2"
    assert printed["config_dir"] == str(second_extra)
    assert list(printed["meters"]) == ["main", "second", "extra_2", "extra_3"]
    assert printed["meters"]["main"] is None
    assert printed["meters"]["second"]["weekly_used_percent"] == 95.0
    assert printed["meters"]["extra_2"]["weekly_used_percent"] == 20.0
    assert printed["meters"]["extra_3"]["weekly_used_percent"] == 40.0


def test_should_wait_for_first_usable_reset_when_all_extras_are_full(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_extra = tmp_path / "first"
    second_extra = tmp_path / "next"
    third_extra = tmp_path / "last"
    readings = {
        first_extra: meters(
            session_used=90.0,
            weekly_used=95.0,
            weekly_resets_in=timedelta(hours=1),
            session_resets_in=timedelta(hours=3),
        ),
        second_extra: meters(
            session_used=10.0, weekly_used=95.0, weekly_resets_in=timedelta(hours=2)
        ),
        third_extra: meters(
            session_used=90.0, weekly_used=10.0, weekly_resets_in=timedelta(days=4),
            session_resets_in=timedelta(hours=4),
        ),
    }
    monkeypatch.setattr(
        choice, "read_account_meters", lambda path: readings.get(path.parent)
    )

    assert choice.main(
        [
            "--main-config-dir",
            str(tmp_path / "main"),
            "--second-config-dir",
            str(first_extra),
            "--extra-config-dir",
            str(second_extra),
            "--extra-config-dir",
            str(third_extra),
        ]
    ) == 0
    printed = json.loads(capsys.readouterr().out)

    assert printed["account"] == choice.CHOICE_WAIT
    assert printed["config_dir"] is None
    assert (NOW + timedelta(hours=2)).isoformat() in printed["reason"]
    assert (NOW + timedelta(hours=1)).isoformat() not in printed["reason"]
    assert list(printed["meters"]) == ["main", "second", "extra_2", "extra_3"]


def test_should_reject_duplicate_extra_config_directories(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        choice.main(
            [
                "--second-config-dir",
                str(tmp_path / "first"),
                "--extra-config-dir",
                str(tmp_path / "first"),
            ]
        )

    assert error.value.code == 2
