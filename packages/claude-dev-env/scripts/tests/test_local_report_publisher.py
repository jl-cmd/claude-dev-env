from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from local_report_publisher import PublicationOutcome, publish_local_report
from local_verification.config import BASE_PLACEHOLDER
from local_verification.manifest import load_manifest
from local_verification.runner import run_verification
from pr_verification.github import GitHubApi, HttpReply
from pr_verification.model import RepositorySettings, StatusState


class RecordingRequester:
    def __init__(self, all_replies: list[HttpReply]) -> None:
        self.all_replies = all_replies
        self.all_requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> HttpReply:
        self.all_requests.append((method, url, headers, body))
        return self.all_replies.pop(0)


def _assert_request_methods(
    requester: RecordingRequester, expected_methods: str
) -> None:
    request_methods = " ".join(
        each_request[0] for each_request in requester.all_requests
    )
    assert request_methods == expected_methods


def _run_git(repository_path: Path, *all_arguments: str) -> str:
    completed_process = subprocess.run(
        ["git", "-C", str(repository_path), *all_arguments],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed_process.returncode == 0, completed_process.stderr
    return completed_process.stdout.strip()


def _create_git_repository(tmp_path: Path) -> tuple[Path, str]:
    repository_path = tmp_path / "repository"
    repository_path.mkdir()
    _run_git(repository_path, "init", "--quiet")
    _run_git(repository_path, "config", "user.email", "tests@example.com")
    _run_git(repository_path, "config", "user.name", "Local Verification Tests")
    (repository_path / "tracked.txt").write_text("stable\n", encoding="utf-8")
    _run_git(repository_path, "add", "tracked.txt")
    _run_git(repository_path, "commit", "--quiet", "-m", "initial")
    return repository_path, _run_git(repository_path, "rev-parse", "HEAD")


def _repository() -> RepositorySettings:
    return RepositorySettings("owner/repository", "https://github.test/repository.git")


def _pull_payload(
    head_sha: str, base_sha: str, merge_sha: str | None = "merge"
) -> bytes:
    return json.dumps(
        {
            "number": 7,
            "draft": False,
            "merge_commit_sha": merge_sha,
            "base": {"ref": "main", "sha": base_sha},
            "head": {"sha": head_sha},
        }
    ).encode("utf-8")


def _candidate_replies(
    head_sha: str, base_sha: str, merge_sha: str | None = "merge"
) -> list[HttpReply]:
    return [
        HttpReply(200, {}, _pull_payload(head_sha, base_sha, merge_sha)),
        HttpReply(
            200,
            {},
            json.dumps({"object": {"sha": base_sha}}).encode("utf-8"),
        ),
    ]


def _advisory_replies(
    head_sha: str, base_sha: str, merge_sha: str | None = "merge"
) -> list[HttpReply]:
    return [
        *_candidate_replies(head_sha, base_sha, merge_sha),
        HttpReply(200, {}, b'[{"name":"local-checks:passed"}]'),
        HttpReply(204, {}, b""),
        HttpReply(201, {}, b"{}"),
    ]


def _write_manifest(
    manifest_path: Path,
    check_arguments: list[str],
    minimum_tests: int | None = None,
    timeout_seconds: float = 10.0,
) -> None:
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "selected",
                        "argv": check_arguments,
                        "cwd": ".",
                        "timeout_seconds": timeout_seconds,
                        **(
                            {"minimum_tests": minimum_tests}
                            if minimum_tests is not None
                            else {}
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _run_report(
    tmp_path: Path,
    check_arguments: list[str],
    minimum_tests: int | None = None,
    timeout_seconds: float = 10.0,
    base_revision: str | None = None,
) -> tuple[Path, Path, str, str]:
    repository_path, base_sha = _create_git_repository(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, check_arguments, minimum_tests, timeout_seconds)
    manifest = load_manifest(manifest_path)
    report_path = tmp_path / "report.json"
    report = run_verification(
        manifest, repository_path, base_revision or base_sha, report_path
    )
    assert report.head_revision is not None
    return repository_path, manifest_path, base_sha, report.head_revision


def _base_check_arguments() -> list[str]:
    return [
        sys.executable,
        "-c",
        "import sys; assert len(sys.argv[1]) == 40",
        BASE_PLACEHOLDER,
    ]


def _assert_recorded_base(report_path: Path, base_sha: str) -> None:
    report_fields = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_fields["checks"][0]["argv"][-1] == base_sha


def _publish_report(
    repository_path: Path,
    manifest_path: Path,
    report_path: Path,
    requester: RecordingRequester,
) -> PublicationOutcome:
    return publish_local_report(
        GitHubApi("https://api.github.test", "token", requester),
        _repository(),
        7,
        repository_path,
        manifest_path,
        report_path,
    )


def _missing_key_arguments(tmp_path: Path) -> list[str]:
    return [
        "--api-url",
        "https://api.github.test",
        "--app-id",
        "42",
        "--installation-id",
        "84",
        "--private-key-path",
        str(tmp_path / "missing.pem"),
        "--repository",
        "owner/repository",
        "--pull-number",
        "7",
        "--local-repo",
        str(tmp_path),
        "--manifest",
        str(tmp_path / "manifest.json"),
        "--report",
        str(tmp_path / "report.json"),
    ]


def test_publishes_success_for_matching_clean_report(tmp_path: Path) -> None:
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path, _base_check_arguments(), base_revision="HEAD"
    )
    _assert_recorded_base(tmp_path / "report.json", base_sha)
    requester = RecordingRequester(
        [
            *_candidate_replies(head_sha, base_sha),
            *_candidate_replies(head_sha, base_sha),
            HttpReply(201, {}, b"{}"),
            HttpReply(200, {}, b"[]"),
            *_candidate_replies(head_sha, base_sha),
        ]
    )
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.SUCCESS
    assert outcome.publishable is True
    assert "Selected local checks passed (1 checks)" == outcome.description
    _assert_request_methods(requester, "GET GET GET GET POST POST GET GET")
    assert requester.all_requests[1][1].endswith("/git/ref/heads/main")
    assert requester.all_requests[4][1].endswith(f"/statuses/{head_sha}")


def test_failed_report_removes_pass_label_and_posts_failure(tmp_path: Path) -> None:
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path, [sys.executable, "-c", "raise SystemExit(4)"]
    )
    requester = RecordingRequester(_advisory_replies(head_sha, base_sha))
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.FAILURE
    assert outcome.publishable is False
    _assert_request_methods(requester, "GET GET GET DELETE POST")
    assert requester.all_requests[2][1].endswith(
        "/issues/7/labels?per_page=100&page=1"
    )
    assert requester.all_requests[3][1].endswith(
        "/issues/7/labels/local-checks%3Apassed"
    )


def test_failed_execution_with_collection_floor_posts_failure(tmp_path: Path) -> None:
    failing_test_path = tmp_path / "test_failure.py"
    failing_test_path.write_text(
        "def test_selected():\n    assert False\n",
        encoding="utf-8",
    )
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path,
        [sys.executable, "-m", "pytest", str(failing_test_path)],
        1,
    )
    requester = RecordingRequester(_advisory_replies(head_sha, base_sha))
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.FAILURE
    assert outcome.publishable is False


def test_incomplete_report_posts_error_without_pass_label(tmp_path: Path) -> None:
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path, ["missing-command"]
    )
    requester = RecordingRequester(_advisory_replies(head_sha, base_sha))
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.ERROR
    assert outcome.publishable is False
    assert [each_request[0] for each_request in requester.all_requests[-3:]] == [
        "GET",
        "DELETE",
        "POST",
    ]


def test_timeout_after_collection_posts_error(tmp_path: Path) -> None:
    sleeping_test_path = tmp_path / "test_timeout.py"
    sleeping_test_path.write_text(
        "import time\ndef test_slow():\n    time.sleep(1)\n",
        encoding="utf-8",
    )
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path,
        [sys.executable, "-m", "pytest", str(sleeping_test_path)],
        1,
        0.1,
    )
    requester = RecordingRequester(_advisory_replies(head_sha, base_sha))
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.ERROR
    assert outcome.publishable is False


def test_collection_failure_posts_error(tmp_path: Path) -> None:
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path,
        [sys.executable, "-m", "pytest", str(tmp_path / "missing_tests.py")],
        1,
    )
    requester = RecordingRequester(_advisory_replies(head_sha, base_sha))
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.ERROR
    assert outcome.publishable is False


def test_advisory_reads_pull_request_without_merge_commit(tmp_path: Path) -> None:
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path, [sys.executable, "-c", "raise SystemExit(4)"]
    )
    requester = RecordingRequester(
        _advisory_replies(head_sha, base_sha, merge_sha=None)
    )
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.FAILURE
    assert outcome.publishable is False


def test_wrong_manifest_removes_pass_label_and_posts_error(tmp_path: Path) -> None:
    repository_path, _manifest_path, base_sha, head_sha = _run_report(
        tmp_path, [sys.executable, "-c", "pass"]
    )
    wrong_manifest_path = tmp_path / "wrong-manifest.json"
    _write_manifest(wrong_manifest_path, [sys.executable, "-c", "pass"])
    wrong_manifest_text = wrong_manifest_path.read_text(encoding="utf-8")
    wrong_manifest_path.write_text(
        wrong_manifest_text.replace('"selected"', '"other"'),
        encoding="utf-8",
    )
    requester = RecordingRequester(_advisory_replies(head_sha, base_sha))
    outcome = _publish_report(
        repository_path, wrong_manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.ERROR
    assert outcome.publishable is False
    _assert_request_methods(requester, "GET GET GET DELETE POST")


def test_success_drift_after_label_removes_label_and_posts_error(
    tmp_path: Path,
) -> None:
    repository_path, manifest_path, base_sha, head_sha = _run_report(
        tmp_path, [sys.executable, "-c", "pass"]
    )
    changed_head = "changed-head"
    requester = RecordingRequester(
        [
            *_candidate_replies(head_sha, base_sha),
            *_candidate_replies(head_sha, base_sha),
            HttpReply(201, {}, b"{}"),
            HttpReply(200, {}, b"[]"),
            *_candidate_replies(changed_head, base_sha),
            HttpReply(200, {}, b'[{"name":"local-checks:passed"}]'),
            HttpReply(204, {}, b""),
            HttpReply(201, {}, b"{}"),
        ]
    )
    outcome = _publish_report(
        repository_path, manifest_path, tmp_path / "report.json", requester
    )

    assert outcome.status == StatusState.ERROR
    assert outcome.publishable is False
    assert [each_request[0] for each_request in requester.all_requests[-3:]] == [
        "GET",
        "DELETE",
        "POST",
    ]
