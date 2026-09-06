from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

TEST_DIRECTORY = Path(__file__).resolve().parent
if str(TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TEST_DIRECTORY))

from automatic_advisory import cli as advisory_cli
from automatic_advisory.model import AdvisoryState
from pr_verification.lock import SupervisorLockError


class _CycleFailsOnceRunner:
    def __init__(self, cycle_error: Exception) -> None:
        self.cycle_error = cycle_error
        self.all_cycles: list[str] = []

    def run_once(self, should_rerun: bool = False) -> tuple[AdvisoryState, ...]:
        self.all_cycles.append("cycle")
        if len(self.all_cycles) == 1:
            raise self.cycle_error
        return (
            AdvisoryState(
                "JonEcho/python-automation",
                3087,
                "passed",
                "unchanged remote head and base",
                None,
                None,
                "2026-09-06T16:00:00+00:00",
                None,
                "report.json",
            ),
        )


def _stop_polling_on_the_second_sleep(
    all_sleeps: list[float],
) -> Callable[[float], None]:
    def sleeper(poll_seconds: float) -> None:
        all_sleeps.append(poll_seconds)
        if len(all_sleeps) == 2:
            raise KeyboardInterrupt

    return sleeper


@pytest.mark.parametrize(
    "cycle_error",
    [
        SupervisorLockError("supervisor lock is held by another owner"),
        OSError("state file is temporarily unavailable"),
    ],
)
def test_polling_reports_a_failed_cycle_and_runs_the_next_cycle(
    cycle_error: Exception,
    tmp_path: Path,
) -> None:
    advisory_runner = _CycleFailsOnceRunner(cycle_error)
    all_sleeps: list[float] = []
    stdout = io.StringIO()

    exit_code = advisory_cli.run_polling(
        advisory_runner,
        1.5,
        stdout,
        tmp_path / "poll-errors.log",
        _stop_polling_on_the_second_sleep(all_sleeps),
    )

    assert exit_code == 0
    assert advisory_runner.all_cycles == ["cycle", "cycle"]
    assert all_sleeps == [1.5, 1.5]
    all_lines = stdout.getvalue().splitlines()
    assert json.loads(all_lines[0]) == {"poll_error": str(cycle_error)}
    assert json.loads(all_lines[1])["status"] == "passed"


class _EveryCycleFailsRunner:
    def __init__(self, cycle_error: Exception) -> None:
        self.cycle_error = cycle_error
        self.all_cycles: list[str] = []

    def run_once(self, should_rerun: bool = False) -> tuple[AdvisoryState, ...]:
        self.all_cycles.append("cycle")
        raise self.cycle_error


def _stop_polling_after(cycle_limit: int) -> Callable[[float], None]:
    all_sleeps: list[float] = []

    def sleeper(poll_seconds: float) -> None:
        all_sleeps.append(poll_seconds)
        if len(all_sleeps) == cycle_limit:
            raise KeyboardInterrupt

    return sleeper


def test_polling_logs_the_failed_cycle_line_beside_the_state_files(
    tmp_path: Path,
) -> None:
    cycle_error = SupervisorLockError("supervisor lock is held by another owner")
    poll_error_log_path = tmp_path / "state" / "poll-errors.log"

    exit_code = advisory_cli.run_polling(
        _EveryCycleFailsRunner(cycle_error),
        1.5,
        io.StringIO(),
        poll_error_log_path,
        _stop_polling_after(1),
    )

    assert exit_code == 0
    all_lines = poll_error_log_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(each_line) for each_line in all_lines] == [
        {"poll_error": str(cycle_error)}
    ]


class _NumberedFailuresRunner:
    def __init__(self) -> None:
        self.all_cycles: list[str] = []

    def run_once(self, should_rerun: bool = False) -> tuple[AdvisoryState, ...]:
        self.all_cycles.append("cycle")
        raise OSError(f"state file is unavailable on cycle {len(self.all_cycles)}")


def test_poll_error_log_keeps_the_newest_two_hundred_lines(tmp_path: Path) -> None:
    poll_error_log_path = tmp_path / "poll-errors.log"

    advisory_cli.run_polling(
        _NumberedFailuresRunner(),
        0.0,
        io.StringIO(),
        poll_error_log_path,
        _stop_polling_after(250),
    )

    all_lines = poll_error_log_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(each_line)["poll_error"] for each_line in all_lines] == [
        f"state file is unavailable on cycle {each_cycle}"
        for each_cycle in range(51, 251)
    ]


def test_poll_error_log_holding_non_utf8_bytes_leaves_the_poller_running(
    tmp_path: Path,
) -> None:
    poll_error_log_path = tmp_path / "poll-errors.log"
    poll_error_log_path.write_bytes(b"\xff\xfe not a utf-8 line\n")
    advisory_runner = _EveryCycleFailsRunner(OSError("state file is unavailable"))

    exit_code = advisory_cli.run_polling(
        advisory_runner,
        0.0,
        io.StringIO(),
        poll_error_log_path,
        _stop_polling_after(1),
    )

    assert exit_code == 0
    assert advisory_runner.all_cycles == ["cycle"]
    all_lines = poll_error_log_path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()
    assert json.loads(all_lines[-1]) == {"poll_error": "state file is unavailable"}


def test_poll_error_log_line_read_value_error_leaves_the_poller_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_value_error(poll_error_log_path: Path) -> list[str]:
        raise ValueError("the log holds bytes no decoder accepts")

    monkeypatch.setattr(advisory_cli, "_poll_error_log_lines", raise_value_error)
    advisory_runner = _EveryCycleFailsRunner(OSError("state file is unavailable"))

    exit_code = advisory_cli.run_polling(
        advisory_runner,
        0.0,
        io.StringIO(),
        tmp_path / "poll-errors.log",
        _stop_polling_after(2),
    )

    assert exit_code == 0
    assert advisory_runner.all_cycles == ["cycle", "cycle"]


def test_poll_error_log_that_cannot_be_written_leaves_the_poller_running(
    tmp_path: Path,
) -> None:
    unwritable_log_path = tmp_path / "state.json" / "poll-errors.log"
    unwritable_log_path.parent.write_text("not a directory\n", encoding="utf-8")
    advisory_runner = _EveryCycleFailsRunner(OSError("state file is unavailable"))

    exit_code = advisory_cli.run_polling(
        advisory_runner,
        0.0,
        io.StringIO(),
        unwritable_log_path,
        _stop_polling_after(2),
    )

    assert exit_code == 0
    assert advisory_runner.all_cycles == ["cycle", "cycle"]
