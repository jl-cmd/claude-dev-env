from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from automatic_advisory import configuration as advisory_configuration
from automatic_advisory.model import (
    AdvisoryRegistration,
    AdvisorySettings,
    ChildOutcome,
)
from automatic_advisory.runner import (
    AdvisoryGitHub,
    AutomaticAdvisoryRunner,
    Publication,
    run_verification_child,
)
from pr_verification.model import PullRequestCandidate, RepositorySettings

VALID_ADVISORY_SETTINGS_TEMPLATE = '{"version":1,"app_id":1,"installation_id":1,"private_key_path":"$ROOT","poll_seconds":0.25,"child_timeout_seconds":45.5,"registrations":[{"repository":"owner/repository","pull_request":1,"checkout":"$ROOT","manifest":"manifest.json","report":"$ROOT","state":"$ROOT","base_ref":"main","remote":"origin"}]}'


class FakeGitHub(AdvisoryGitHub):
    def __init__(self, candidate: PullRequestCandidate) -> None:
        self.candidate = candidate
        self.all_events: list[str] = []
        self.all_merge_requirements: list[bool] = []
        self.remove_label_failures = 0

    def list_open_candidates(
        self,
        repository: RepositorySettings,
        *,
        should_require_merge_commit: bool = True,
    ) -> tuple[PullRequestCandidate, ...]:
        self.all_merge_requirements.append(should_require_merge_commit)
        return (self.candidate,)

    def remove_label(
        self, repository: RepositorySettings, pull_request_number: int, label: str
    ) -> None:
        self.all_events.append("remove-label")
        if self.remove_label_failures:
            self.remove_label_failures -= 1
            raise RuntimeError("label service unavailable")


class FakePublication:
    def __init__(self, status: str) -> None:
        self.status = status
        self.description = "local check finished"


def _run_git(repository_path: Path, *arguments: str) -> str:
    completed_process = subprocess.run(
        ["git", "-C", str(repository_path), *arguments],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed_process.returncode == 0, completed_process.stderr
    return completed_process.stdout.strip()


def _build_checkout(tmp_path: Path) -> tuple[Path, str]:
    checkout_path = tmp_path / "checkout"
    remote_path = tmp_path / "remote.git"
    checkout_path.mkdir()
    _initialize_checkout(checkout_path)
    _write_checkout_files(checkout_path)
    _run_git(checkout_path, "add", "tracked.txt")
    _run_git(checkout_path, "add", "manifest.json")
    _run_git(checkout_path, "add", ".github/ci/local_verify.py")
    _run_git(checkout_path, "commit", "--quiet", "-m", "test")
    _create_bare_remote(checkout_path, remote_path)
    return checkout_path, _run_git(checkout_path, "rev-parse", "HEAD")


def _initialize_checkout(checkout_path: Path) -> None:
    _run_git(checkout_path, "init", "--quiet")
    hooks_directory = checkout_path / ".test-hooks"
    hooks_directory.mkdir()
    _run_git(checkout_path, "config", "--local", "core.hooksPath", str(hooks_directory))
    _run_git(checkout_path, "checkout", "-b", "main")
    _run_git(checkout_path, "config", "user.email", "test@example.com")
    _run_git(checkout_path, "config", "user.name", "Automatic Advisory Test")


def _write_checkout_files(checkout_path: Path) -> None:
    (checkout_path / "tracked.txt").write_text("clean\n", encoding="utf-8")
    (checkout_path / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "real-child",
                        "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                        "cwd": ".",
                        "timeout_seconds": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _write_local_verify_wrapper(checkout_path)


def _write_local_verify_wrapper(checkout_path: Path) -> None:
    wrapper_path = checkout_path / ".github" / "ci" / "local_verify.py"
    wrapper_path.parent.mkdir(parents=True)
    wrapper_path.write_text(
        "import argparse\n"
        "import os\n"
        "from pathlib import Path\n"
        "import subprocess\n"
        "import sys\n"
        "if os.environ.get('PYTEST_XDIST_AUTO_NUM_WORKERS') != '2':\n"
        "    raise SystemExit(9)\n"
        "if str(Path.cwd()) not in os.environ.get('PYTHONPATH', '').split(os.pathsep):\n"
        "    raise SystemExit(10)\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--base', required=True)\n"
        "parser.add_argument('--executor', required=True)\n"
        "parser.add_argument('--output', required=True)\n"
        "arguments = parser.parse_args()\n"
        "selected_manifest_path = Path(arguments.output).with_name(Path(arguments.output).stem + '.selected-manifest.json')\n"
        "selected_manifest_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "selected_manifest_path.write_text(Path('manifest.json').read_text(encoding='utf-8'), encoding='utf-8')\n"
        "raise SystemExit(subprocess.call([\n"
        "    sys.executable, arguments.executor, '--manifest', 'manifest.json',\n"
        "    '--repo', '.', '--base', arguments.base, '--output', arguments.output\n"
        "]))\n",
        encoding="utf-8",
    )


def _create_bare_remote(checkout_path: Path, remote_path: Path) -> None:
    _run_git(
        checkout_path,
        "clone",
        "--bare",
        str(checkout_path),
        str(remote_path),
    )
    _run_git(checkout_path, "remote", "add", "origin", str(remote_path))


def _build_registration(tmp_path: Path, checkout_path: Path) -> AdvisoryRegistration:
    manifest_path = checkout_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "real-child",
                        "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                        "cwd": ".",
                        "timeout_seconds": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return AdvisoryRegistration(
        RepositorySettings("JonEcho/python-automation", "unused"),
        2985,
        checkout_path,
        PurePosixPath("manifest.json"),
        tmp_path / "reports" / "pr-2985.json",
        tmp_path / "state" / "pr-2985.json",
        "main",
        "origin",
    )


def _build_candidate(head_sha: str, merge_sha: str = "unused") -> PullRequestCandidate:
    return PullRequestCandidate(
        "JonEcho/python-automation",
        2985,
        "main",
        head_sha,
        head_sha,
        merge_sha,
        False,
    )


def _build_settings(registration: AdvisoryRegistration) -> AdvisorySettings:
    return AdvisorySettings(
        "https://api.github.com",
        4841271,
        159293880,
        registration.state_path.parent / "private-key.pem",
        60.0,
        30.0,
        (registration,),
    )


def _valid_advisory_settings_fields(tmp_path: Path) -> dict[str, object]:
    return json.loads(
        VALID_ADVISORY_SETTINGS_TEMPLATE.replace('"$ROOT"', json.dumps(str(tmp_path)))
    )


def _publish_passed(
    *all_arguments: object,
) -> Publication:
    return FakePublication("passed")


def _run_recorded_child(
    all_events: list[str],
    registration: AdvisoryRegistration,
    base_ref: str,
    timeout_seconds: float,
) -> ChildOutcome:
    all_events.append("child")
    child_outcome = run_verification_child(registration, base_ref, timeout_seconds)
    assert child_outcome.exit_code == 0, child_outcome.stderr_text
    return child_outcome


def _run_counted_child(
    child_calls: list[str],
    registration: AdvisoryRegistration,
    base_ref: str,
    timeout_seconds: float,
) -> ChildOutcome:
    assert registration.checkout_path.is_dir()
    assert base_ref
    assert timeout_seconds > 0
    child_calls.append("child")
    _write_child_artifacts(registration, 0)
    return ChildOutcome(0, "", "", False)


def _write_child_artifacts(
    registration: AdvisoryRegistration,
    exit_code: int,
) -> None:
    registration.report_path.parent.mkdir(parents=True, exist_ok=True)
    registration.report_path.write_text(
        json.dumps({"exit_code": exit_code}),
        encoding="utf-8",
    )
    registration.selected_manifest_path.write_text(
        registration.manifest_absolute_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def _build_counting_runner(
    registration: AdvisoryRegistration,
    github: FakeGitHub,
    child_calls: list[str],
    publisher: Callable[..., Publication],
) -> AutomaticAdvisoryRunner:
    return AutomaticAdvisoryRunner(
        _build_settings(registration),
        github,
        child_runner=lambda child_registration, base_ref, timeout_seconds: (
            _run_counted_child(
                child_calls, child_registration, base_ref, timeout_seconds
            )
        ),
        publisher=publisher,
        clock=lambda: "2026-09-05T00:00:00+00:00",
    )


def _publish_recorded(
    all_events: list[str],
    github: FakeGitHub,
    github_client: object,
    repository: RepositorySettings,
    pull_request_number: int,
    checkout: Path,
    manifest: Path,
    report: Path,
) -> FakePublication:
    all_events.append("publish")
    assert github_client is github
    assert repository.slug == "JonEcho/python-automation"
    assert pull_request_number == 2985
    assert checkout.is_dir()
    assert manifest.is_file()
    assert report.is_file()
    return FakePublication("passed")


def _build_real_runner(
    registration: AdvisoryRegistration,
    github: FakeGitHub,
) -> tuple[AutomaticAdvisoryRunner, list[str]]:
    all_events = github.all_events
    runner = AutomaticAdvisoryRunner(
        _build_settings(registration),
        github,
        child_runner=lambda child_registration, base_ref, timeout_seconds: (
            _run_recorded_child(
                all_events, child_registration, base_ref, timeout_seconds
            )
        ),
        publisher=lambda github_client, repository, pull_request_number, checkout, manifest, report: (
            _publish_recorded(
                all_events,
                github,
                github_client,
                repository,
                pull_request_number,
                checkout,
                manifest,
                report,
            )
        ),
        clock=lambda: "2026-09-05T00:00:00+00:00",
    )
    return runner, all_events


def test_runner_executes_real_child_and_publishes_after_label_removal(
    tmp_path: Path,
) -> None:
    checkout_path, head_sha = _build_checkout(tmp_path)
    registration = _build_registration(tmp_path, checkout_path)
    github = FakeGitHub(_build_candidate(head_sha))
    runner, all_events = _build_real_runner(registration, github)

    state = runner.run_once()[0]

    assert state.status == "passed"
    assert all_events == ["remove-label", "child", "publish"]
    assert (
        json.loads(registration.state_path.read_text(encoding="utf-8"))["head_sha"]
        == head_sha
    )


def test_runner_waits_for_matching_clean_checkout(tmp_path: Path) -> None:
    checkout_path, head_sha = _build_checkout(tmp_path)
    registration = _build_registration(tmp_path, checkout_path)
    github = FakeGitHub(_build_candidate("remote-head"))
    child_calls: list[str] = []
    runner = _build_counting_runner(registration, github, child_calls, _publish_passed)

    state = runner.run_once()[0]

    assert state.status == "waiting"
    assert state.head_sha == "remote-head"
    assert child_calls == []
    assert head_sha != state.head_sha


def test_runner_skips_an_unchanged_published_identity(tmp_path: Path) -> None:
    checkout_path, head_sha = _build_checkout(tmp_path)
    registration = _build_registration(tmp_path, checkout_path)
    github = FakeGitHub(_build_candidate(head_sha))
    child_calls: list[str] = []
    runner = _build_counting_runner(registration, github, child_calls, _publish_passed)

    runner.run_once()
    state = runner.run_once()[0]

    assert state.status == "passed"
    assert child_calls == ["child"]


@pytest.mark.parametrize("field_name", ["poll_seconds", "child_timeout_seconds"])
@pytest.mark.parametrize("invalid_seconds", [float("nan"), float("inf"), float("-inf")])
def test_configuration_rejects_nonfinite_timing(
    tmp_path: Path, field_name: str, invalid_seconds: float
) -> None:
    settings_path = tmp_path / "settings.json"
    all_settings = _valid_advisory_settings_fields(tmp_path)
    settings_path.write_text(json.dumps(all_settings), encoding="utf-8")
    valid_settings = advisory_configuration.load_advisory_settings(settings_path)
    assert valid_settings.poll_seconds == 0.25
    assert valid_settings.child_timeout_seconds == 45.5
    all_settings[field_name] = invalid_seconds
    settings_path.write_text(json.dumps(all_settings), encoding="utf-8")

    with pytest.raises(
        advisory_configuration.AdvisoryConfigurationError,
        match=f"{field_name} must be positive",
    ):
        advisory_configuration.load_advisory_settings(settings_path)
