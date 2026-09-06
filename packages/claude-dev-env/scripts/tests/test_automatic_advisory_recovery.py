from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

TEST_DIRECTORY = Path(__file__).resolve().parent
if str(TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TEST_DIRECTORY))

import test_automatic_advisory as support
from automatic_advisory import cli as advisory_cli
from automatic_advisory import execution
from automatic_advisory.configuration import (
    AdvisoryConfigurationError,
    load_advisory_settings,
)
from automatic_advisory.model import AdvisoryState, ChildOutcome
from automatic_advisory.runner import (
    AdvisoryGitHub,
    AutomaticAdvisoryRunner,
    Publication,
    run_verification_child,
)
from pr_verification.lock import SupervisorLockError


def test_runner_retries_after_dirty_checkout_becomes_clean(tmp_path: Path) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    child_calls: list[str] = []
    dirty_path = checkout_path / "dirty.txt"
    dirty_path.write_text("pending\n", encoding="utf-8")
    runner = support._build_counting_runner(
        registration, github, child_calls, support._publish_passed
    )

    waiting_state = runner.run_once()[0]
    dirty_path.unlink()
    passed_state = runner.run_once()[0]

    assert waiting_state.status == "waiting"
    assert passed_state.status == "passed"
    assert child_calls == ["child"]


def test_runner_retries_after_publication_failure(tmp_path: Path) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    child_calls: list[str] = []
    publication_calls: list[str] = []

    def publish_once_then_pass(*all_arguments: object) -> Publication:
        publication_calls.append("publish")
        if len(publication_calls) == 1:
            raise RuntimeError("temporary publication failure")
        return support.FakePublication("passed")

    runner = support._build_counting_runner(
        registration, github, child_calls, publish_once_then_pass
    )

    failed_state = runner.run_once()[0]
    passed_state = runner.run_once()[0]

    assert failed_state.status == "error"
    assert passed_state.status == "passed"
    assert child_calls == ["child", "child"]
    assert publication_calls == ["publish", "publish"]


def test_runner_retries_after_base_fetch_failure(tmp_path: Path) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    unavailable_registration = replace(registration, remote_name="missing")
    github = support.FakeGitHub(support._build_candidate(head_sha))
    failed_runner = support._build_counting_runner(
        unavailable_registration, github, [], support._publish_passed
    )

    offline_state = failed_runner.run_once()[0]
    recovered_runner = support._build_counting_runner(
        registration, github, [], support._publish_passed
    )
    passed_state = recovered_runner.run_once()[0]

    assert offline_state.status == "offline"
    assert passed_state.status == "passed"


def test_runner_retries_label_invalidation_after_first_failure(
    tmp_path: Path,
) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    github.remove_label_failures = 1
    dirty_path = checkout_path / "dirty.txt"
    dirty_path.write_text("pending\n", encoding="utf-8")
    runner = support._build_counting_runner(
        registration, github, [], support._publish_passed
    )

    error_state = runner.run_once()[0]
    waiting_state = runner.run_once()[0]

    assert error_state.status == "error"
    assert waiting_state.status == "waiting"
    assert github.all_events == ["remove-label", "remove-label"]


def _build_refresh_failure_runner(
    registration: support.AdvisoryRegistration,
    github: support.FakeGitHub,
    factory_calls: list[str],
) -> AutomaticAdvisoryRunner:
    def refresh_github(repository: object) -> AdvisoryGitHub:
        factory_calls.append("refresh")
        if len(factory_calls) > 1:
            raise RuntimeError("temporary GitHub outage")
        return github

    def run_child(
        registration: support.AdvisoryRegistration,
        base_ref: str,
        timeout_seconds: float,
    ) -> ChildOutcome:
        support._write_child_artifacts(registration, 0)
        return ChildOutcome(0, "", "", False)

    runner = AutomaticAdvisoryRunner(
        support._build_settings(registration),
        github,
        github_factory=refresh_github,
        child_runner=run_child,
        publisher=support._publish_passed,
        clock=lambda: "2026-09-05T00:00:00+00:00",
    )
    return runner


def test_runner_keeps_daemon_alive_when_refresh_fails(tmp_path: Path) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    factory_calls: list[str] = []
    runner = _build_refresh_failure_runner(registration, github, factory_calls)

    state = runner.run_once()[0]

    assert state.status == "offline"
    assert factory_calls == ["refresh", "refresh"]


def test_child_start_failure_clears_stale_report(tmp_path: Path) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    registration.report_path.parent.mkdir(parents=True)
    registration.report_path.write_text("stale\n", encoding="utf-8")
    registration.selected_manifest_path.write_text("stale\n", encoding="utf-8")
    (checkout_path / ".github" / "ci" / "local_verify.py").unlink()

    child_outcome = run_verification_child(
        registration,
        head_sha,
        30.0,
    )

    assert child_outcome.exit_code != 0
    assert not registration.report_path.exists()
    assert not registration.selected_manifest_path.exists()


def test_runner_rejects_child_report_exit_code_mismatch(tmp_path: Path) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    publisher_calls: list[str] = []

    def mismatched_child(
        child_registration: support.AdvisoryRegistration,
        base_ref: str,
        timeout_seconds: float,
    ) -> ChildOutcome:
        support._write_child_artifacts(child_registration, 0)
        return ChildOutcome(1, "", "check failed", False)

    def publish(*all_arguments: object) -> Publication:
        publisher_calls.append("publish")
        return support.FakePublication("passed")

    runner = AutomaticAdvisoryRunner(
        support._build_settings(registration),
        github,
        child_runner=mismatched_child,
        publisher=publish,
        clock=lambda: "2026-09-05T00:00:00+00:00",
    )

    state = runner.run_once()[0]
    assert state.status == "error"
    assert publisher_calls == []


def test_runner_removes_pass_label_before_changed_dirty_checkout_waits(
    tmp_path: Path,
) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    child_calls: list[str] = []
    runner = support._build_counting_runner(
        registration, github, child_calls, support._publish_passed
    )

    first_state = runner.run_once()[0]
    (checkout_path / "dirty.txt").write_text("pending\n", encoding="utf-8")
    github.candidate = support._build_candidate("changed-head")
    changed_state = runner.run_once()[0]

    assert first_state.status == "passed"
    assert changed_state.status == "waiting"
    assert github.all_events == ["remove-label", "remove-label"]
    assert child_calls == ["child"]


def test_runner_accepts_open_conflicting_pull_request_candidate(
    tmp_path: Path,
) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha, merge_sha=""))
    runner = support._build_counting_runner(
        registration, github, [], support._publish_passed
    )

    state = runner.run_once()[0]

    assert state.status == "passed"
    assert github.all_merge_requirements == [False]


def test_start_polling_returns_without_waiting_for_detached_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_launches: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def record_launch(
        all_arguments: tuple[object, ...], **launch_options: object
    ) -> None:
        all_launches.append((all_arguments, launch_options))

    monkeypatch.setattr(advisory_cli.subprocess, "Popen", record_launch)

    exit_code = advisory_cli.start_polling(tmp_path / "settings.json")

    assert exit_code == 0
    assert len(all_launches) == 1
    launch_arguments, launch_options = all_launches[0]
    assert launch_arguments[-1] == "--poll"
    assert launch_options["stdin"] is advisory_cli.subprocess.DEVNULL
    assert launch_options["stdout"] is advisory_cli.subprocess.DEVNULL


def test_configuration_rejects_two_pairs_for_one_repository(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    registration = {
        "repository": "JonEcho/python-automation",
        "pull_request": 2985,
        "app_id": 4841271,
        "installation_id": 159293880,
        "private_key_path": str(tmp_path / "private-key.pem"),
        "checkout": str(tmp_path),
        "manifest": "manifest.json",
        "report": str(tmp_path / "report.json"),
        "state": str(tmp_path / "state.json"),
        "base_ref": "main",
        "remote": "origin",
    }
    settings_path.write_text(
        json.dumps({"version": 1, "registrations": [registration, registration]}),
        encoding="utf-8",
    )

    with pytest.raises(AdvisoryConfigurationError, match="one automatic advisory"):
        load_advisory_settings(settings_path)


class _BrokenStartStream:
    def __init__(self) -> None:
        self.close_calls = 0

    def write(self, text: str) -> int:
        raise BrokenPipeError(text)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.close_calls += 1
        raise BrokenPipeError("close")


def test_release_windows_process_host_returns_false_when_stdin_breaks_on_close() -> (
    None
):
    broken_stream = _BrokenStartStream()
    child_process = SimpleNamespace(stdin=broken_stream)

    was_released = execution._release_windows_process_host(child_process)

    assert was_released is False
    assert child_process.stdin is None
    assert broken_stream.close_calls == 1


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


def test_poll_error_log_keeps_the_newest_two_hundred_lines(tmp_path: Path) -> None:
    poll_error_log_path = tmp_path / "poll-errors.log"

    advisory_cli.run_polling(
        _EveryCycleFailsRunner(OSError("state file is temporarily unavailable")),
        0.0,
        io.StringIO(),
        poll_error_log_path,
        _stop_polling_after(250),
    )

    all_lines = poll_error_log_path.read_text(encoding="utf-8").splitlines()
    assert len(all_lines) == 200
    assert json.loads(all_lines[0]) == {
        "poll_error": "state file is temporarily unavailable"
    }


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
