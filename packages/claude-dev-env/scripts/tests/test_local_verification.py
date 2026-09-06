from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from local_verification import check_runner
from local_verification.config.constants import (
    COLLECTION_ERROR_KIND,
    FAILED_STATUS,
    NONZERO_EXIT_ERROR_KIND,
)
from local_verification.manifest import (
    ManifestRunFatal,
    compute_manifest_digest,
    load_manifest,
)
from local_verification.model import (
    CheckSpec,
    CommandCapture,
    ExclusionSpec,
    VerificationManifest,
    VerificationReport,
)
from local_verification.runner import run_verification


def _manifest(*checks: CheckSpec) -> VerificationManifest:
    return VerificationManifest(1, tuple(checks), ())


def _python_check(check_id: str, script_text: str, cwd: str = ".") -> CheckSpec:
    return CheckSpec(check_id, (sys.executable, "-c", script_text), cwd, 10.0)


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


def _assert_check_outputs(report: VerificationReport, output_path: Path) -> None:
    assert report.aggregate_status == "failed"
    assert [each_record.status for each_record in report.checks] == [
        "passed",
        "failed",
        "incomplete",
        "incomplete",
    ]
    assert report.checks[1].exit_code == 7
    assert report.checks[2].error_kind == "missing_tool"
    assert report.checks[3].error_kind == "timeout"
    assert output_path.exists()
    for each_record in report.checks:
        assert each_record.stdout_log.exists()
        assert each_record.stderr_log.exists()
    run_log_path = output_path.with_suffix(".logs") / "run.log"
    assert "aggregate: failed" in run_log_path.read_text(encoding="utf-8")


def test_load_manifest_requires_unique_check_ids(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "same",
                        "argv": ["python"],
                        "cwd": ".",
                        "timeout_seconds": 1,
                    },
                    {
                        "id": "same",
                        "argv": ["python"],
                        "cwd": ".",
                        "timeout_seconds": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestRunFatal, match="unique"):
        load_manifest(manifest_path)


def test_load_manifest_preserves_exclusions_and_collection_floor(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "tests",
                        "argv": ["python", "-m", "pytest"],
                        "cwd": "packages/app",
                        "timeout_seconds": 2,
                        "minimum_tests": 3,
                    }
                ],
                "exclusions": [{"selector": "manual", "reason": "requires a human"}],
            }
        ),
        encoding="utf-8",
    )

    loaded_manifest = load_manifest(manifest_path)

    assert loaded_manifest.checks[0].minimum_tests == 3
    assert loaded_manifest.checks[0].cwd == "packages/app"
    assert loaded_manifest.exclusions == (ExclusionSpec("manual", "requires a human"),)


def test_run_verification_executes_pass_fail_missing_and_timeout_checks(
    tmp_path: Path,
) -> None:
    all_checks = (
        _python_check("passes", ""),
        _python_check("fails", "raise SystemExit(7)"),
        CheckSpec("missing", ("command-that-does-not-exist",), ".", 10.0),
        _python_check("times-out", "import time; time.sleep(2)"),
    )
    timed_check = CheckSpec("times-out", all_checks[-1].command_arguments, ".", 0.1)
    output_path = tmp_path / "reports" / "verification.json"

    report = run_verification(
        _manifest(all_checks[0], all_checks[1], all_checks[2], timed_check),
        tmp_path,
        "base-sha",
        output_path,
    )

    _assert_check_outputs(report, output_path)


def test_run_verification_keeps_argv_spaces_and_runs_outside_caller_directory(
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "repository with spaces"
    repository_path.mkdir()
    script_path = repository_path / "folder with spaces" / "check.py"
    script_path.parent.mkdir()
    script_path.write_text("raise SystemExit(0)\n", encoding="utf-8")
    check = CheckSpec("spaces", (sys.executable, str(script_path)), ".", 10.0)

    report = run_verification(
        _manifest(check),
        repository_path,
        "base-sha",
        tmp_path / "verification.json",
    )

    assert report.aggregate_status == "passed"
    assert report.checks[0].command_arguments == (sys.executable, str(script_path))


def test_run_verification_enforces_minimum_tests_for_pytest(tmp_path: Path) -> None:
    empty_tests = tmp_path / "tests"
    empty_tests.mkdir()
    check = CheckSpec(
        "pytest",
        (sys.executable, "-m", "pytest", "tests"),
        ".",
        30.0,
        1,
    )

    report = run_verification(
        _manifest(check),
        tmp_path,
        "base-sha",
        tmp_path / "verification.json",
    )

    assert report.aggregate_status == "failed"
    assert report.checks[0].status == "failed"
    assert report.checks[0].error_kind == "minimum_tests"
    assert report.checks[0].collected_tests == 0


def test_run_verification_rejects_all_required_tests_skipped(tmp_path: Path) -> None:
    skipped_test_path = tmp_path / "test_skipped.py"
    skipped_test_path.write_text(
        """import pytest

@pytest.mark.skip(reason="requires service")
def test_required_service():
    pass
""",
        encoding="utf-8",
    )
    check = CheckSpec(
        "pytest",
        (sys.executable, "-m", "pytest", "test_skipped.py"),
        ".",
        30.0,
        1,
    )

    report = run_verification(
        _manifest(check),
        tmp_path,
        "base-sha",
        tmp_path / "verification.json",
    )

    assert report.aggregate_status == "incomplete"
    assert report.checks[0].error_kind == "skipped_tests"
    assert report.checks[0].collected_tests == 1
    assert report.checks[0].exit_code == 0


def test_run_verification_records_publishable_clean_git_revision(
    tmp_path: Path,
) -> None:
    repository_path, base_revision = _create_git_repository(tmp_path)
    check = _python_check("passes", "")
    manifest = _manifest(check)
    output_path = tmp_path / "verification.json"

    report = run_verification(
        manifest,
        repository_path,
        base_revision,
        output_path,
    )

    assert report.head_revision == base_revision
    assert report.base_revision == base_revision
    assert report.manifest_digest == compute_manifest_digest(manifest)
    assert report.worktree_clean is True
    assert report.inputs_unchanged is True
    assert report.publishable is True
    report_mapping = json.loads(output_path.read_text(encoding="utf-8"))
    assert report_mapping["head"] == base_revision
    assert report_mapping["base"] == base_revision
    assert report_mapping["manifest_digest"] == report.manifest_digest
    assert report_mapping["publishable"] is True


def test_run_verification_keeps_dirty_git_candidate_advisory(
    tmp_path: Path,
) -> None:
    repository_path, base_revision = _create_git_repository(tmp_path)
    (repository_path / "untracked.txt").write_text("local\n", encoding="utf-8")

    report = run_verification(
        _manifest(_python_check("passes", "")),
        repository_path,
        base_revision,
        tmp_path / "verification.json",
    )

    assert report.aggregate_status == "passed"
    assert report.worktree_clean is False
    assert report.inputs_unchanged is True
    assert report.publishable is False


def test_run_verification_invalidates_git_candidate_when_head_changes(
    tmp_path: Path,
) -> None:
    repository_path, base_revision = _create_git_repository(tmp_path)
    tracked_path = repository_path / "tracked.txt"
    commit_script = (
        "from pathlib import Path; import subprocess; "
        f"Path({str(tracked_path)!r}).write_text('changed\\n'); "
        f"subprocess.run(['git', '-C', {str(repository_path)!r}, 'add', 'tracked.txt'], check=True); "
        f"subprocess.run(['git', '-C', {str(repository_path)!r}, 'commit', '--quiet', '-m', 'check'], check=True)"
    )

    report = run_verification(
        _manifest(_python_check("changes-head", commit_script)),
        repository_path,
        base_revision,
        tmp_path / "verification.json",
    )

    assert report.aggregate_status == "passed"
    assert report.head_revision == base_revision
    assert _run_git(repository_path, "rev-parse", "HEAD") != base_revision
    assert report.inputs_unchanged is False
    assert report.publishable is False


def test_run_verification_never_publishes_failed_or_incomplete_git_checks(
    tmp_path: Path,
) -> None:
    repository_path, base_revision = _create_git_repository(tmp_path)
    all_checks = (
        _python_check("fails", "raise SystemExit(4)"),
        CheckSpec("missing", ("missing-command",), ".", 10.0),
    )

    report = run_verification(
        _manifest(*all_checks),
        repository_path,
        base_revision,
        tmp_path / "verification.json",
    )

    assert report.aggregate_status == "failed"
    assert [each_record.status for each_record in report.checks] == [
        "failed",
        "incomplete",
    ]
    assert report.publishable is False


def test_failed_command_keeps_failed_status_when_collection_also_fails() -> None:
    check = CheckSpec("unit", ("pytest",), ".", 10.0, minimum_tests=1)
    failed_collection = CommandCapture(1, "", "", COLLECTION_ERROR_KIND, "no collect")

    status, error_kind, _ = check_runner._classify_collection(
        check, (failed_collection, None), FAILED_STATUS, NONZERO_EXIT_ERROR_KIND, "x"
    )

    assert (status, error_kind) == (FAILED_STATUS, NONZERO_EXIT_ERROR_KIND)
