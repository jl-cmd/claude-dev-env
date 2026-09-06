from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TESTS_DIRECTORY))

import test_automatic_advisory as support
from automatic_advisory import cli, git, publisher
from pr_verification.model import RepositorySettings, StatusState

PROCESS_RUNNER_TIMEOUT_SECONDS = 10.0
PRODUCTION_CHILD_TIMEOUT_SECONDS = 3.0
PROCESS_EXIT_WAIT_SECONDS = 2.0
PROCESS_POLL_SECONDS = 0.05


class _SuccessfulPublicationAdapter:
    status = StatusState.SUCCESS
    description = "passed"


def _publisher_module_recording_paths(
    all_published_manifest_paths: list[Path],
) -> SimpleNamespace:
    def record_publication(
        _github: object,
        _repository: RepositorySettings,
        _pull_request_number: int,
        _checkout_path: Path,
        manifest_path: Path,
        _report_path: Path,
    ) -> _SuccessfulPublicationAdapter:
        all_published_manifest_paths.append(manifest_path)
        return _SuccessfulPublicationAdapter()

    return SimpleNamespace(publish_local_report=record_publication)


def _build_counted_runner(
    registration: support.AdvisoryRegistration,
    github: support.FakeGitHub,
    child_calls: list[str],
) -> support.AutomaticAdvisoryRunner:
    def run_child(
        child_registration: support.AdvisoryRegistration,
        base_ref: str,
        timeout_seconds: float,
    ) -> support.ChildOutcome:
        return support._run_counted_child(
            child_calls,
            child_registration,
            base_ref,
            timeout_seconds,
        )

    return support.AutomaticAdvisoryRunner(
        support._build_settings(registration),
        github,
        child_runner=run_child,
        clock=lambda: "2026-09-05T00:00:00+00:00",
    )


def _build_recovering_cli_runner(
    monkeypatch: pytest.MonkeyPatch,
    registration: support.AdvisoryRegistration,
    github: support.FakeGitHub,
    authentication_attempts: list[str],
    child_calls: list[str],
) -> support.AutomaticAdvisoryRunner:
    def issue_repository_api(*arguments: object, **options: object) -> object:
        authentication_attempts.append("attempt")
        if len(authentication_attempts) == 1:
            raise RuntimeError("offline")
        return github

    monkeypatch.setattr(cli, "_issue_repository_api", issue_repository_api)
    runner = cli._build_runner(support._build_settings(registration))
    counted_runner = _build_counted_runner(registration, github, child_calls)
    runner.child_runner = counted_runner.child_runner
    runner.publisher = support._publish_passed
    return runner


def _run_report_only_child(
    registration: support.AdvisoryRegistration,
) -> support.ChildOutcome:
    registration.report_path.parent.mkdir(parents=True, exist_ok=True)
    registration.report_path.write_text(
        json.dumps({"exit_code": 0}),
        encoding="utf-8",
    )
    return support.ChildOutcome(0, "", "", False)


def _record_unexpected_publication(
    publisher_calls: list[str],
    *all_arguments: object,
) -> support.Publication:
    publisher_calls.append("publish")
    return support.FakePublication("passed")


def test_publisher_adapter_returns_github_status_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class PublicationAdapter:
        status = StatusState.SUCCESS
        description = "passed"

    class PublisherModule:
        publish_local_report = staticmethod(lambda *arguments: PublicationAdapter())

    monkeypatch.setattr(publisher, "import_module", lambda name: PublisherModule)
    registration = support._build_registration(tmp_path, tmp_path)
    publication = publisher._publish_report(
        object(),
        registration.repository,
        registration.pull_request_number,
        registration.checkout_path,
        registration.manifest_absolute_path,
        registration.report_path,
    )

    assert publication.status == "success"


def test_real_publisher_adapter_runs_once_for_unchanged_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_published_manifest_paths: list[Path] = []
    publisher_module = _publisher_module_recording_paths(all_published_manifest_paths)
    monkeypatch.setattr(publisher, "import_module", lambda name: publisher_module)
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    child_calls: list[str] = []
    runner = _build_counted_runner(registration, github, child_calls)
    first_state = runner.run_once()[0]
    second_state = runner.run_once()[0]

    assert first_state.status == "passed"
    assert second_state.status == "passed"
    assert child_calls == ["child"]
    assert all_published_manifest_paths == [registration.selected_manifest_path]


def test_build_runner_run_once_persists_offline_then_recovers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    authentication_attempts: list[str] = []
    child_calls: list[str] = []
    runner = _build_recovering_cli_runner(
        monkeypatch,
        registration,
        github,
        authentication_attempts,
        child_calls,
    )

    assert authentication_attempts == []
    offline_state = runner.run_once()[0]
    persisted_offline_state = json.loads(
        registration.state_path.read_text(encoding="utf-8")
    )
    passed_state = runner.run_once()[0]

    assert offline_state.status == "offline"
    assert persisted_offline_state["status"] == "offline"
    assert passed_state.status == "passed"
    assert authentication_attempts == ["attempt", "attempt", "attempt"]
    assert child_calls == ["child"]


def test_runner_marks_missing_selected_manifest_incomplete(tmp_path: Path) -> None:
    checkout_path, head_sha = support._build_checkout(tmp_path)
    registration = support._build_registration(tmp_path, checkout_path)
    github = support.FakeGitHub(support._build_candidate(head_sha))
    publisher_calls: list[str] = []

    runner = support.AutomaticAdvisoryRunner(
        support._build_settings(registration),
        github,
        child_runner=lambda child_registration, _base_ref, _timeout_seconds: (
            _run_report_only_child(child_registration)
        ),
        publisher=lambda *all_arguments: _record_unexpected_publication(
            publisher_calls,
            *all_arguments,
        ),
        clock=lambda: "2026-09-05T00:00:00+00:00",
    )

    state = runner.run_once()[0]

    assert state.status == "error"
    assert state.reason == "verification child did not produce a report"
    assert publisher_calls == []


def test_fetch_base_returns_false_after_git_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registration = support._build_registration(tmp_path, tmp_path)
    candidate = support._build_candidate("head")
    captured_options: dict[str, object] = {}

    def timeout_run(*arguments: object, **options: object) -> object:
        captured_options.update(options)
        raise subprocess.TimeoutExpired("git", 30.0)

    monkeypatch.setattr(git.subprocess, "run", timeout_run)

    assert git._fetch_base(registration, candidate) is False
    assert captured_options["timeout"] == 30.0
    captured_environment = captured_options["env"]
    assert isinstance(captured_environment, dict)
    assert captured_environment.get("GIT_TERMINAL_PROMPT") == "0"


def test_fetch_base_updates_dedicated_and_remote_tracking_refs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registration = support._build_registration(tmp_path, tmp_path)
    candidate = support._build_candidate("head")
    all_fetch_arguments: list[tuple[str, ...]] = []

    def record_fetch(
        fetch_arguments: tuple[str, ...],
        **options: object,
    ) -> subprocess.CompletedProcess[bytes]:
        all_fetch_arguments.append(fetch_arguments)
        return subprocess.CompletedProcess(fetch_arguments, 0, b"", b"")

    monkeypatch.setattr(git.subprocess, "run", record_fetch)

    assert git._fetch_base(registration, candidate) is True
    assert all_fetch_arguments == [
        (
            "git",
            "fetch",
            "--force",
            "--no-tags",
            "origin",
            "+refs/heads/main:refs/cde/advisory-base/2985",
            "+refs/heads/main:refs/remotes/origin/main",
        )
    ]


def _build_descendant_parent_script(
    descendant_identifier_path: Path,
    parent_action: str,
) -> str:
    descendant_script = "import time; time.sleep(30)"
    return (
        "import subprocess,sys,time\n"
        "from pathlib import Path\n"
        f"child_process = subprocess.Popen((sys.executable, '-c', {descendant_script!r}))\n"
        f"Path({str(descendant_identifier_path)!r}).write_text(str(child_process.pid), encoding='utf-8')\n"
        f"{parent_action}\n"
    )


def _build_process_runner_script(
    checkout_path: Path,
    descendant_identifier_path: Path,
    parent_action: str,
) -> str:
    parent_script = _build_descendant_parent_script(
        descendant_identifier_path,
        parent_action,
    )
    return (
        "import os,sys\n"
        "from pathlib import Path\n"
        "from types import SimpleNamespace\n"
        "from automatic_advisory import execution\n"
        f"registration = SimpleNamespace(checkout_path=Path({str(checkout_path)!r}))\n"
        "scripts_directory = Path(execution.__file__).resolve().parents[1]\n"
        "child_environment = execution._build_child_environment(registration, scripts_directory)\n"
        "child_process = execution._start_child_process(\n"
        f"    (sys.executable, '-c', {parent_script!r}), registration, child_environment\n"
        ")\n"
        "if child_process is None:\n"
        "    raise SystemExit(2)\n"
        f"child_outcome = execution._collect_child_outcome(child_process, {PRODUCTION_CHILD_TIMEOUT_SECONDS!r})\n"
        "if not child_outcome.timed_out:\n"
        "    raise SystemExit(3)\n"
    )


def _is_process_running(process_identifier: int) -> bool:
    if sys.platform == "win32":
        completed_process = subprocess.run(
            ("tasklist", "/FI", f"PID eq {process_identifier}", "/FO", "CSV", "/NH"),
            capture_output=True,
            check=False,
            text=True,
            timeout=PROCESS_EXIT_WAIT_SECONDS,
        )
        return f'"{process_identifier}"' in completed_process.stdout
    try:
        os.kill(process_identifier, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_exit(process_identifier: int) -> bool:
    deadline = time.monotonic() + PROCESS_EXIT_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not _is_process_running(process_identifier):
            return True
        time.sleep(PROCESS_POLL_SECONDS)
    return not _is_process_running(process_identifier)


def _end_process_for_test(process_identifier: int) -> None:
    if not _is_process_running(process_identifier):
        return
    if sys.platform == "win32":
        subprocess.run(
            ("taskkill", "/T", "/F", "/PID", str(process_identifier)),
            capture_output=True,
            check=False,
            timeout=PROCESS_EXIT_WAIT_SECONDS,
        )
        return
    os.kill(process_identifier, signal.SIGKILL)


@pytest.mark.parametrize(
    "parent_action",
    ("time.sleep(30)", "raise SystemExit(0)"),
    ids=("timed-parent", "exited-parent"),
)
def test_production_launch_timeout_ends_descendant_and_keeps_runner_alive(
    tmp_path: Path,
    parent_action: str,
) -> None:
    descendant_identifier_path = tmp_path / "descendant.pid"
    runner_script = _build_process_runner_script(
        tmp_path,
        descendant_identifier_path,
        parent_action,
    )
    completed_runner = subprocess.run(
        (sys.executable, "-c", runner_script),
        cwd=support.SCRIPTS_DIRECTORY,
        capture_output=True,
        check=False,
        text=True,
        timeout=PROCESS_RUNNER_TIMEOUT_SECONDS,
    )
    assert descendant_identifier_path.is_file(), completed_runner.stderr
    descendant_identifier = int(descendant_identifier_path.read_text(encoding="utf-8"))

    try:
        assert completed_runner.returncode == 0, completed_runner.stderr
        assert _wait_for_process_exit(descendant_identifier)
    finally:
        _end_process_for_test(descendant_identifier)


def test_detached_start_resolves_relative_settings_before_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_launches: list[tuple[tuple[str, ...], dict[str, object]]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli.subprocess,
        "Popen",
        lambda arguments, **options: all_launches.append((tuple(arguments), options)),
    )

    assert cli.start_polling(Path("settings.json")) == 0

    launch_arguments = all_launches[0][0]
    assert launch_arguments[launch_arguments.index("--settings") + 1] == str(
        tmp_path / "settings.json"
    )
