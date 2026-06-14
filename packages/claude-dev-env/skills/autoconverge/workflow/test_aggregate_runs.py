"""Tests for aggregate_runs against the real wf_881252e6-700 fixture run tree."""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aggregate_runs
import render_report

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "wf_run"
FIXTURE_RUN_ID = "wf_881252e6-700"
FIXTURE_PR_NUMBER = 211
FIXTURE_OWNER = "example-owner"
FIXTURE_REPO = "example-repo"


def _copy_fixture_run(projects_root: Path, session_name: str) -> Path:
    """Copy the fixture run tree into projects_root/proj/<session> and return its journal."""
    session_dir = projects_root / "proj" / session_name
    shutil.copytree(FIXTURE_DIR, session_dir)
    return session_dir / "workflows" / f"{FIXTURE_RUN_ID}.json"


def _write_minimal_run(
    projects_root: Path,
    session_name: str,
    run_id: str,
    pr_number: int,
    resolve_heads: int,
) -> Path:
    """Write a transcript-free autoconverge journal with N resolve-head entries."""
    workflows_dir = projects_root / "proj" / session_name / "workflows"
    workflows_dir.mkdir(parents=True)
    progress = [
        {
            "index": each_index + 1,
            "label": render_report.LABEL_RESOLVE_HEAD,
            "agentId": None,
        }
        for each_index in range(resolve_heads)
    ]
    journal = {
        "runId": run_id,
        "timestamp": "2026-06-14T00:00:00.000Z",
        "workflowName": "autoconverge",
        "args": json.dumps(
            {"owner": FIXTURE_OWNER, "repo": FIXTURE_REPO, "prNumber": pr_number}
        ),
        "result": {
            "converged": False,
            "rounds": resolve_heads,
            "finalSha": "",
            "blocker": None,
        },
        "workflowProgress": progress,
    }
    journal_path = workflows_dir / f"{run_id}.json"
    journal_path.write_text(json.dumps(journal, indent=2), encoding="utf-8")
    return journal_path


def test_aggregate_single_run_reproduces_loader_counts(tmp_path: Path) -> None:
    """Should reproduce the single-run finding, round, and fix counts when only one journal exists."""
    projects_root = tmp_path / "projects"
    seed_journal = _copy_fixture_run(projects_root, "session-a")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    result = aggregate_runs.aggregate_pr_journals(
        seed_journal, FIXTURE_OWNER, FIXTURE_REPO, FIXTURE_PR_NUMBER, work_dir
    )

    assert result.round_count == 4
    assert len(result.findings) == 15
    assert result.final_sha.startswith("7c2f420c")
    run_data = render_report.load_run_data(result.combined_journal_path)
    assert run_data.total_finding_count == 15
    assert run_data.fix_commit_count == 2


def test_aggregate_two_runs_sums_rounds(tmp_path: Path) -> None:
    """Should sum resolve-head rounds across every journal for the same PR."""
    projects_root = tmp_path / "projects"
    seed_journal = _copy_fixture_run(projects_root, "session-a")
    _write_minimal_run(projects_root, "session-b", "wf_extra-001", FIXTURE_PR_NUMBER, 2)
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    result = aggregate_runs.aggregate_pr_journals(
        seed_journal, FIXTURE_OWNER, FIXTURE_REPO, FIXTURE_PR_NUMBER, work_dir
    )

    assert result.round_count == 6
    assert len(result.findings) == 15
    assert result.final_sha.startswith("7c2f420c")


def test_discover_filters_by_owner_repo_and_pr_number(tmp_path: Path) -> None:
    """Should return only journals whose args match the requested owner, repo, and PR."""
    projects_root = tmp_path / "projects"
    _copy_fixture_run(projects_root, "session-a")
    _write_minimal_run(projects_root, "session-other", "wf_other-001", 999, 1)

    discovered = aggregate_runs.discover_pr_journals(
        projects_root, FIXTURE_OWNER, FIXTURE_REPO, FIXTURE_PR_NUMBER
    )

    assert len(discovered) == 1
    assert discovered[0].stem == FIXTURE_RUN_ID
