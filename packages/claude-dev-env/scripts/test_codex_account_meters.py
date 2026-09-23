"""Tests for the reader of one Codex account's rate-limit windows."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from codex_account_meters import (
    CodexMeterUnreadError,
    exchange_with_app_server,
    parse_rate_limits_reply,
    read_codex_meters,
    request_messages,
    resolve_codex_path,
)

RESET_SECONDS = 1790000000


def reply_line(rate_limits: object) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": 2, "result": {"rateLimits": rate_limits}}
    )


class TestParseRateLimitsReply:
    def should_measure_room_by_the_tightest_window(self) -> None:
        meters = parse_rate_limits_reply(
            reply_line(
                {
                    "primary": {
                        "usedPercent": 30,
                        "windowDurationMins": 300,
                        "resetsAt": RESET_SECONDS,
                    },
                    "secondary": {
                        "usedPercent": 85,
                        "windowDurationMins": 10080,
                        "resetsAt": RESET_SECONDS,
                    },
                }
            )
        )
        assert meters.percent_left == 15.0
        assert [each.duration_minutes for each in meters.all_windows] == [300, 10080]
        assert meters.all_windows[0].resets_at == datetime.fromtimestamp(
            RESET_SECONDS, tz=timezone.utc
        )

    def should_read_a_reply_with_one_window(self) -> None:
        meters = parse_rate_limits_reply(
            reply_line(
                {
                    "primary": None,
                    "secondary": {"usedPercent": 40, "windowDurationMins": 10080},
                }
            )
        )
        assert meters.percent_left == 60.0

    def should_clamp_used_percent_past_full(self) -> None:
        meters = parse_rate_limits_reply(reply_line({"primary": {"usedPercent": 130}}))
        assert meters.percent_left == 0.0

    @pytest.mark.parametrize(
        "line",
        [
            "not json",
            json.dumps({"id": 2, "error": {"message": "not signed in"}}),
            reply_line({"primary": None, "secondary": None}),
            reply_line({"primary": {"usedPercent": "high"}}),
            json.dumps({"id": 2, "result": {}}),
        ],
    )
    def should_raise_unread_for_a_reply_without_a_usable_window(
        self, line: str
    ) -> None:
        with pytest.raises(CodexMeterUnreadError):
            parse_rate_limits_reply(line)


class TestShortWindowPercentLeft:
    def should_read_the_room_left_in_the_five_hour_window(self) -> None:
        meters = parse_rate_limits_reply(
            reply_line(
                {
                    "primary": {"usedPercent": 70, "windowDurationMins": 300},
                    "secondary": {"usedPercent": 20, "windowDurationMins": 10080},
                }
            )
        )
        assert meters.short_window_percent_left == 30.0

    def should_name_no_short_window_for_a_weekly_only_account(self) -> None:
        meters = parse_rate_limits_reply(
            reply_line({"secondary": {"usedPercent": 20, "windowDurationMins": 10080}})
        )
        assert meters.short_window_percent_left is None


class TestBlockingReset:
    def should_name_when_the_last_blocking_window_resets(self) -> None:
        meters = parse_rate_limits_reply(
            reply_line(
                {
                    "primary": {"usedPercent": 95, "resetsAt": RESET_SECONDS},
                    "secondary": {"usedPercent": 99, "resetsAt": RESET_SECONDS + 3600},
                }
            )
        )
        assert meters.resets_before_room(10.0) == datetime.fromtimestamp(
            RESET_SECONDS + 3600, tz=timezone.utc
        )


class TestReadCodexMeters:
    def should_send_the_handshake_then_the_read_under_the_home(self) -> None:
        all_calls: list[tuple[Path, Path, list[str]]] = []

        def fake_exchange(
            codex_path: Path,
            codex_home: Path,
            all_messages: Sequence[Mapping[str, object]],
        ) -> list[str]:
            all_calls.append(
                (
                    codex_path,
                    codex_home,
                    [str(each.get("method")) for each in all_messages],
                )
            )
            return [
                json.dumps({"id": 1, "result": {}}),
                reply_line({"primary": {"usedPercent": 20}}),
            ]

        meters = read_codex_meters(Path("codex"), Path("profiles") / "codex-1", fake_exchange)
        assert meters.percent_left == 80.0
        assert all_calls == [
            (
                Path("codex"),
                Path("profiles") / "codex-1",
                ["initialize", "initialized", "account/rateLimits/read"],
            )
        ]

    def should_raise_unread_when_the_server_never_answers(self) -> None:
        with pytest.raises(CodexMeterUnreadError):
            read_codex_meters(
                Path("codex"), Path("/h"), lambda *_: [json.dumps({"id": 1})]
            )

    def should_raise_unread_when_the_server_cannot_start(self) -> None:
        def broken_exchange(*_: object) -> list[str]:
            raise FileNotFoundError("codex")

        with pytest.raises(CodexMeterUnreadError):
            read_codex_meters(Path("codex"), Path("/h"), broken_exchange)


FAKE_APP_SERVER = """#!/usr/bin/env python3
import json, os, sys
for line in sys.stdin:
    message = json.loads(line)
    if message.get("id") == 2:
        used = 12 if os.environ.get("CODEX_HOME", "").endswith("codex-2") else 99
        print(json.dumps({"id": 2, "result": {"rateLimits": {"primary": {"usedPercent": used}}}}), flush=True)
"""


class TestExchangeWithAppServer:
    @pytest.mark.skipif(os.name == "nt", reason="the fake server runs through a shebang")
    def should_read_the_reply_while_input_stays_open(self, tmp_path: Path) -> None:
        fake_codex = tmp_path / "codex"
        fake_codex.write_text(FAKE_APP_SERVER)
        fake_codex.chmod(0o755)

        meters = read_codex_meters(fake_codex, tmp_path / "codex-2", exchange_with_app_server)

        assert meters.percent_left == 88.0


class TestRequestMessages:
    def should_ask_for_rate_limits_after_the_handshake(self) -> None:
        all_messages = request_messages()
        assert [each.get("id") for each in all_messages] == [1, None, 2]
        assert all_messages[2]["method"] == "account/rateLimits/read"


class TestResolveCodexPath:
    def should_use_the_named_path(self, tmp_path: Path) -> None:
        assert resolve_codex_path(tmp_path / "codex.exe") == tmp_path / "codex.exe"

    def should_raise_when_no_codex_is_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH", "")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(FileNotFoundError):
            resolve_codex_path(None)
