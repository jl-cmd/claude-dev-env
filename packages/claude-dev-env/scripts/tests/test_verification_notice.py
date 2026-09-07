from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS_DIRECTORY = Path(__file__).resolve().parents[2] / "hooks" / "git-hooks"
NOTICE_SCRIPT = HOOKS_DIRECTORY / "verification_notice.py"
ALL_REMOTE_URLS = (
    "https://github.com/JonEcho/python-automation.git",
    "git@github.com:JonEcho/python-automation.git",
    "ssh://git@github.com/JonEcho/python-automation.git",
)


def run_notice(
    repository_path: Path,
    event_name: str = "commit",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(NOTICE_SCRIPT),
            "--event",
            event_name,
            "--repo",
            str(repository_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def create_target_repository(
    temporary_directory: Path,
    remote_url: str,
) -> tuple[Path, str]:
    repository_path = temporary_directory / "Jon Echo project with spaces Ω"
    repository_path.mkdir(parents=True)
    run_git(repository_path, "init", "--quiet")
    run_git(repository_path, "config", "user.email", "test@example.invalid")
    run_git(repository_path, "config", "user.name", "Verification Test")
    (repository_path / "README.md").write_text("check\n", encoding="utf-8")
    run_git(repository_path, "add", "README.md")
    run_git(repository_path, "commit", "--quiet", "-m", "initial")
    run_git(repository_path, "remote", "add", "origin", remote_url)
    current_head = run_git(repository_path, "rev-parse", "HEAD").stdout.strip()
    return repository_path, current_head


def run_git(
    repository_path: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def write_report(
    repository_path: Path,
    report_fields: dict[str, object],
) -> None:
    manifest_path = repository_path / "config" / "local-verification.json"
    manifest_path.parent.mkdir(exist_ok=True)
    manifest_mapping = {
        "version": 1,
        "checks": [
            {
                "id": "smoke",
                "argv": ["python", "-c", "pass"],
                "cwd": ".",
                "timeout_seconds": 1.0,
                "minimum_tests": None,
            }
        ],
        "exclusions": [],
    }
    manifest_path.write_text(json.dumps(manifest_mapping), encoding="utf-8")
    report_path = repository_path / ".git" / "local-verification" / "report.json"
    report_path.parent.mkdir(exist_ok=True)
    all_report_fields = {
        "selection": {"selected_manifest_path": "config/local-verification.json"},
        "manifest_digest": hashlib.sha256(
            json.dumps(manifest_mapping, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        **report_fields,
    }
    report_path.write_text(json.dumps(all_report_fields), encoding="utf-8")


def write_passing_report(repository_path: Path) -> str:
    write_report(repository_path, {})
    run_git(repository_path, "add", "config/local-verification.json")
    run_git(repository_path, "commit", "--quiet", "-m", "manifest")
    current_head = run_git(repository_path, "rev-parse", "HEAD").stdout.strip()
    run_git(repository_path, "update-ref", "refs/remotes/origin/main", current_head)
    write_report(
        repository_path,
        {
            "head": current_head,
            "base": current_head,
            "worktree_clean": True,
            "inputs_unchanged": True,
            "publishable": True,
            "status": "passed",
            "aggregate": {
                "status": "passed",
                "total": 1,
                "passed": 1,
                "failed": 0,
                "incomplete": 0,
                "exit_code": 0,
            },
        },
    )
    return current_head


def write_worktree_passing_report(
    repository_path: Path,
    linked_git_directory: Path,
) -> str:
    current_head = run_git(repository_path, "rev-parse", "HEAD").stdout.strip()
    source_manifest_path = repository_path / "config" / "local-verification.json"
    source_report_path = repository_path / ".git" / "local-verification" / "report.json"
    metadata_directory = linked_git_directory / "local-verification"
    metadata_directory.mkdir(parents=True, exist_ok=True)
    metadata_manifest_path = metadata_directory / "local-verification.json"
    metadata_manifest_path.write_bytes(source_manifest_path.read_bytes())
    all_report_fields = json.loads(source_report_path.read_text(encoding="utf-8"))
    all_report_fields["selection"]["selected_manifest_path"] = str(
        metadata_manifest_path
    )
    metadata_report_path = metadata_directory / "report.json"
    metadata_report_path.write_text(json.dumps(all_report_fields), encoding="utf-8")
    return current_head


def test_notice_matches_remote_formats_and_quotes_paths(tmp_path: Path) -> None:
    for each_index, each_remote_url in enumerate(ALL_REMOTE_URLS):
        repository_path, current_head = create_target_repository(
            tmp_path / str(each_index), each_remote_url
        )
        completed_notice = run_notice(repository_path, "push")
        assert completed_notice.returncode == 0
        assert "LOCAL VERIFICATION ADVISORY" in completed_notice.stdout
        assert f"Current SHA: {current_head}" in completed_notice.stdout
        assert "State: pending" in completed_notice.stdout
        assert "python '" in completed_notice.stdout
        wrapper_suffix = str(Path(".github") / "ci" / "local_verify.py")
        assert f"{wrapper_suffix}' --base origin/main" in completed_notice.stdout
        assert "--executor '" in completed_notice.stdout
        assert "--output '" in completed_notice.stdout
        assert repository_path.name in completed_notice.stdout
        assert "--base origin/main" in completed_notice.stdout
        assert "does not block commit or push" in completed_notice.stdout


def test_notice_reports_pending_when_manifest_exists_without_report(
    tmp_path: Path,
) -> None:
    repository_path, _ = create_target_repository(
        tmp_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    write_report(repository_path, {})
    (repository_path / ".git" / "local-verification" / "report.json").unlink()

    completed_notice = run_notice(repository_path)

    assert completed_notice.returncode == 0
    assert "State: pending" in completed_notice.stdout
    assert "manifest is missing or unreadable" not in completed_notice.stdout
    assert "No complete current pass is recorded" in completed_notice.stdout


def test_notice_ignores_unrelated_remote(tmp_path: Path) -> None:
    repository_path, _ = create_target_repository(
        tmp_path,
        "https://github.com/other-owner/other-repository.git",
    )
    completed_notice = run_notice(repository_path)
    assert completed_notice.returncode == 0
    assert completed_notice.stdout == ""


def test_notice_reports_failed_checks_without_pass_label(tmp_path: Path) -> None:
    repository_path, current_head = create_target_repository(
        tmp_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    write_report(repository_path, {"head": current_head, "status": "failed"})
    completed_notice = run_notice(repository_path)
    assert completed_notice.returncode == 0
    assert f"Current SHA: {current_head}" in completed_notice.stdout
    assert "State: failed" in completed_notice.stdout
    assert "recorded local checks failed" in completed_notice.stdout
    assert "local-checks:passed" not in completed_notice.stdout


def test_notice_reports_pass_only_for_complete_current_revision(tmp_path: Path) -> None:
    repository_path, _ = create_target_repository(
        tmp_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    current_head = write_passing_report(repository_path)
    completed_notice = run_notice(repository_path)
    assert completed_notice.returncode == 0
    assert f"Verified SHA: {current_head}" in completed_notice.stdout
    assert "State: passed" in completed_notice.stdout
    assert (
        "local-checks:passed is valid only for this exact current SHA"
        in completed_notice.stdout
    )


def test_notice_handles_malformed_report_and_missing_repository(tmp_path: Path) -> None:
    repository_path, _ = create_target_repository(
        tmp_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    manifest_path = repository_path / "config" / "local-verification.json"
    manifest_path.parent.mkdir(exist_ok=True)
    manifest_mapping = {
        "version": 1,
        "checks": [
            {
                "id": "smoke",
                "argv": ["python", "-c", "pass"],
                "cwd": ".",
                "timeout_seconds": 1.0,
                "minimum_tests": None,
            }
        ],
        "exclusions": [],
    }
    manifest_path.write_text(json.dumps(manifest_mapping), encoding="utf-8")
    report_path = repository_path / ".git" / "local-verification" / "report.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_bytes(b"not-json\xff")
    malformed_notice = run_notice(repository_path)
    missing_notice = run_notice(tmp_path / "missing repository")
    assert malformed_notice.returncode == 0
    assert "State: unverified" in malformed_notice.stdout
    assert missing_notice.returncode == 0
    assert missing_notice.stdout == ""


def test_notice_uses_worktree_specific_report_path(tmp_path: Path) -> None:
    repository_path, _ = create_target_repository(
        tmp_path / "main",
        "https://github.com/JonEcho/python-automation.git",
    )
    linked_worktree_path = tmp_path / "linked worktree Ω"
    run_git(repository_path, "worktree", "add", "--detach", str(linked_worktree_path))
    linked_git_directory = Path(
        run_git(linked_worktree_path, "rev-parse", "--absolute-git-dir").stdout.strip()
    )

    completed_notice = run_notice(linked_worktree_path)

    expected_report_path = linked_git_directory / "local-verification" / "report.json"
    shared_report_path = repository_path / ".git" / "local-verification" / "report.json"
    assert completed_notice.returncode == 0
    assert str(expected_report_path) in completed_notice.stdout
    assert str(shared_report_path) not in completed_notice.stdout


def test_notice_accepts_complete_report_in_worktree_metadata(tmp_path: Path) -> None:
    repository_path, _ = create_target_repository(
        tmp_path / "main",
        "https://github.com/JonEcho/python-automation.git",
    )
    current_head = write_passing_report(repository_path)
    linked_worktree_path = tmp_path / "linked worktree Ω"
    run_git(repository_path, "worktree", "add", "--detach", str(linked_worktree_path))
    linked_git_directory = Path(
        run_git(linked_worktree_path, "rev-parse", "--absolute-git-dir").stdout.strip()
    )
    write_worktree_passing_report(repository_path, linked_git_directory)

    completed_notice = run_notice(linked_worktree_path)

    future_path = linked_worktree_path / "future.txt"
    future_path.write_text("future\n", encoding="utf-8")
    run_git(linked_worktree_path, "add", "future.txt")
    run_git(linked_worktree_path, "commit", "--quiet", "-m", "future")
    future_head = run_git(linked_worktree_path, "rev-parse", "HEAD").stdout.strip()
    stale_notice = run_notice(linked_worktree_path)
    run_git(linked_worktree_path, "reset", "--quiet", "--hard", current_head)
    run_git(linked_worktree_path, "update-ref", "refs/remotes/origin/main", future_head)
    moved_base_notice = run_notice(linked_worktree_path)

    assert "State: passed" in completed_notice.stdout
    assert f"Verified SHA: {current_head}" in completed_notice.stdout
    assert "State: stale" in stale_notice.stdout
    assert "State: unverified" in moved_base_notice.stdout


def test_notice_invalidates_pass_after_worktree_edit(tmp_path: Path) -> None:
    repository_path, _ = create_target_repository(
        tmp_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    current_head = write_passing_report(repository_path)
    passed_notice = run_notice(repository_path)
    (repository_path / "untracked.txt").write_text("changed\n", encoding="utf-8")

    changed_notice = run_notice(repository_path)

    assert f"Verified SHA: {current_head}" in passed_notice.stdout
    assert "State: passed" in passed_notice.stdout
    assert "Verified SHA: none" in changed_notice.stdout
    assert "State: unverified" in changed_notice.stdout


def test_notice_invalidates_pass_after_origin_base_moves(tmp_path: Path) -> None:
    repository_path, _ = create_target_repository(
        tmp_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    current_head = write_passing_report(repository_path)
    passed_notice = run_notice(repository_path)
    (repository_path / "future.txt").write_text("future\n", encoding="utf-8")
    run_git(repository_path, "add", "future.txt")
    run_git(repository_path, "commit", "--quiet", "-m", "future")
    future_head = run_git(repository_path, "rev-parse", "HEAD").stdout.strip()
    run_git(repository_path, "reset", "--quiet", "--hard", current_head)
    run_git(repository_path, "update-ref", "refs/remotes/origin/main", future_head)

    moved_base_notice = run_notice(repository_path)

    assert "State: passed" in passed_notice.stdout
    assert "Verified SHA: none" in moved_base_notice.stdout
    assert "State: unverified" in moved_base_notice.stdout
