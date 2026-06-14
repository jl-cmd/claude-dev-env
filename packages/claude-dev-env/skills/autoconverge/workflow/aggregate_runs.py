"""Merge every autoconverge run journal for one PR into a single combined journal."""

import argparse
import json
import os
import re
import shutil
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import convergence_summary
import render_report
from autoconverge_report_constants.render_report_constants import (
    ARGS_FIELD_OWNER,
    ARGS_FIELD_PR_NUMBER,
    ARGS_FIELD_REPO,
    COMBINED_RUN_ID_PREFIX,
    JOURNAL_FIELD_ARGS,
    JOURNAL_FIELD_RESULT,
    JOURNAL_FIELD_RUN_ID,
    JOURNAL_FIELD_TIMESTAMP,
    JOURNAL_FIELD_WORKFLOW_NAME,
    JOURNAL_FIELD_WORKFLOW_PROGRESS,
    JOURNAL_SIBLING_SUBAGENTS,
    JOURNAL_SIBLING_WORKFLOWS,
    LABEL_RESOLVE_HEAD,
    ONEXC_PYTHON_MAJOR_VERSION,
    ONEXC_PYTHON_MINOR_VERSION,
    PROGRESS_FIELD_AGENT_ID,
    PROGRESS_FIELD_LABEL,
    PROJECTS_DIR_NAME,
    RESULT_FIELD_FINAL_SHA,
    SUMMARY_DETAIL_MAX_CHARS,
    WORKFLOW_NAME_AUTOCONVERGE,
)


@dataclass(frozen=True)
class AggregateResult:
    """The combined journal plus the aggregated inputs a closing report needs."""

    combined_journal_path: Path
    findings: list[dict]
    fix_summaries: list[str]
    round_count: int
    final_sha: str


def _parse_args_object(journal: dict) -> dict:
    """Return the journal's args as a dict, parsing a JSON string when needed.

    Args:
        journal: A parsed run-journal object.

    Returns:
        The args object as a dict, or an empty dict when absent or unparseable.
    """
    raw_args = journal.get(JOURNAL_FIELD_ARGS, "")
    if isinstance(raw_args, dict):
        return raw_args
    try:
        parsed = json.loads(raw_args)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_projects_root(seed_journal_path: Path) -> Path:
    """Return the projects directory that contains the seed run journal.

    Args:
        seed_journal_path: Path to one of the PR's wf_<runId>.json journals.

    Returns:
        The nearest ancestor directory named 'projects', or the seed's
        four-levels-up ancestor when no such ancestor exists.
    """
    for each_ancestor in seed_journal_path.parents:
        if each_ancestor.name == PROJECTS_DIR_NAME:
            return each_ancestor
    return seed_journal_path.parents[3]


def _discover_pr_runs(
    projects_root: Path, owner: str, repo: str, pr_number: int
) -> list[tuple[Path, dict]]:
    """Return every autoconverge (journal path, journal) pair for the PR, oldest first.

    Args:
        projects_root: The projects directory holding all run trees.
        owner: The PR's repository owner.
        repo: The PR's repository name.
        pr_number: The PR number.

    Returns:
        A timestamp-sorted list of (journal path, parsed journal) pairs.
    """
    runs: list[tuple[Path, dict]] = []
    for each_journal_path in projects_root.glob("*/*/workflows/wf_*.json"):
        try:
            journal = json.loads(each_journal_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if journal.get(JOURNAL_FIELD_WORKFLOW_NAME) != WORKFLOW_NAME_AUTOCONVERGE:
            continue
        args_object = _parse_args_object(journal)
        matches_pr = (
            args_object.get(ARGS_FIELD_OWNER) == owner
            and args_object.get(ARGS_FIELD_REPO) == repo
            and args_object.get(ARGS_FIELD_PR_NUMBER) == pr_number
        )
        if matches_pr:
            runs.append((each_journal_path, journal))
    runs.sort(key=lambda pair: pair[1].get(JOURNAL_FIELD_TIMESTAMP, ""))
    return runs


def discover_pr_journals(
    projects_root: Path, owner: str, repo: str, pr_number: int
) -> list[Path]:
    """Return every autoconverge journal path for the PR, oldest first.

    Args:
        projects_root: The projects directory holding all run trees.
        owner: The PR's repository owner.
        repo: The PR's repository name.
        pr_number: The PR number.

    Returns:
        A timestamp-sorted list of journal paths matching the PR.
    """
    return [
        path
        for path, _journal in _discover_pr_runs(projects_root, owner, repo, pr_number)
    ]


def _retry_after_chmod(
    remove_func: Callable[[str], None], failing_path: str, *_exc_info: object
) -> None:
    """Clear the Windows read-only bit on a path, then retry the removal that failed.

    Args:
        remove_func: The os removal call rmtree was attempting when it failed.
        failing_path: The path the failed removal call could not delete.
        _exc_info: The exception or exc_info tuple the rmtree handler passes.
    """
    os.chmod(failing_path, stat.S_IWRITE)
    remove_func(failing_path)


def _select_rmtree_handler_keyword() -> dict[str, Callable[..., None]]:
    """Return the rmtree retry-handler keyword argument for the running Python.

    Returns:
        A single-entry dict using the 'onexc' keyword on the Python versions that
        accept it and 'onerror' on the earlier versions that do not.
    """
    onexc_required_version = (ONEXC_PYTHON_MAJOR_VERSION, ONEXC_PYTHON_MINOR_VERSION)
    if sys.version_info >= onexc_required_version:
        return {"onexc": _retry_after_chmod}
    return {"onerror": _retry_after_chmod}


def _force_remove(target_path: Path) -> None:
    """Remove a directory tree, clearing the Windows read-only bit on failure.

    Args:
        target_path: The directory tree to remove when it exists.
    """
    if not target_path.exists():
        return
    handler_keyword = _select_rmtree_handler_keyword()
    if "onexc" in handler_keyword:
        shutil.rmtree(target_path, onexc=_retry_after_chmod)
        return
    shutil.rmtree(target_path, onerror=_retry_after_chmod)


def aggregate_pr_journals(
    seed_journal_path: Path, owner: str, repo: str, pr_number: int, work_dir: Path
) -> AggregateResult:
    """Merge every autoconverge journal for the PR into one combined journal.

    Args:
        seed_journal_path: One of the PR's run journals, used to locate the rest.
        owner: The PR's repository owner.
        repo: The PR's repository name.
        pr_number: The PR number.
        work_dir: A directory the combined run tree is written under.

    Returns:
        An AggregateResult carrying the combined journal path, the deduped
        findings, the fix summaries, the resolve-head round count, and the
        final commit sha drawn from the latest run's result.
    """
    projects_root = _resolve_projects_root(seed_journal_path)
    runs = _discover_pr_runs(projects_root, owner, repo, pr_number)

    combined_run_id = f"{COMBINED_RUN_ID_PREFIX}{pr_number}"
    dest_base = work_dir / combined_run_id
    _force_remove(dest_base)
    combined_workflows_dir = dest_base / JOURNAL_SIBLING_WORKFLOWS
    combined_workflows_dir.mkdir(parents=True)
    combined_agents_dir = (
        dest_base
        / JOURNAL_SIBLING_SUBAGENTS
        / JOURNAL_SIBLING_WORKFLOWS
        / combined_run_id
    )
    combined_agents_dir.mkdir(parents=True)

    combined_progress: list[dict] = []
    final_sha = ""
    latest_timestamp = ""
    for each_journal_path, each_journal in runs:
        source_agents_dir = (
            each_journal_path.parent.parent
            / JOURNAL_SIBLING_SUBAGENTS
            / JOURNAL_SIBLING_WORKFLOWS
            / each_journal_path.stem
        )
        for each_entry in each_journal.get(JOURNAL_FIELD_WORKFLOW_PROGRESS, []):
            agent_id = each_entry.get(PROGRESS_FIELD_AGENT_ID)
            if agent_id:
                source_transcript = source_agents_dir / f"agent-{agent_id}.jsonl"
                if source_transcript.exists():
                    shutil.copy(
                        source_transcript,
                        combined_agents_dir / f"agent-{agent_id}.jsonl",
                    )
            combined_progress.append(each_entry)
        result_block = each_journal.get(JOURNAL_FIELD_RESULT) or {}
        if result_block.get(RESULT_FIELD_FINAL_SHA):
            final_sha = result_block[RESULT_FIELD_FINAL_SHA]
        timestamp = each_journal.get(JOURNAL_FIELD_TIMESTAMP, "")
        if timestamp > latest_timestamp:
            latest_timestamp = timestamp

    round_count = sum(
        1
        for each_entry in combined_progress
        if each_entry.get(PROGRESS_FIELD_LABEL) == LABEL_RESOLVE_HEAD
    )
    combined_journal = {
        JOURNAL_FIELD_RUN_ID: combined_run_id,
        JOURNAL_FIELD_TIMESTAMP: latest_timestamp,
        JOURNAL_FIELD_WORKFLOW_NAME: WORKFLOW_NAME_AUTOCONVERGE,
        JOURNAL_FIELD_ARGS: json.dumps(
            {
                ARGS_FIELD_OWNER: owner,
                ARGS_FIELD_REPO: repo,
                ARGS_FIELD_PR_NUMBER: pr_number,
            }
        ),
        JOURNAL_FIELD_RESULT: {RESULT_FIELD_FINAL_SHA: final_sha},
        JOURNAL_FIELD_WORKFLOW_PROGRESS: combined_progress,
    }
    combined_journal_path = combined_workflows_dir / f"{combined_run_id}.json"
    combined_journal_path.write_text(json.dumps(combined_journal), encoding="utf-8")

    run_data = render_report.load_run_data(combined_journal_path)
    findings = [
        {
            "severity": each_finding.severity,
            "category": each_finding.category,
            "file": each_finding.file,
            "line": each_finding.line,
            "title": each_finding.title,
            "detail": (each_finding.detail or "")[:SUMMARY_DETAIL_MAX_CHARS],
        }
        for each_finding in run_data.all_distinct_findings
    ]
    fix_summaries = [
        each_fix.summary
        for each_fix in run_data.fix_by_round.values()
        if each_fix.summary
    ]
    return AggregateResult(
        combined_journal_path=combined_journal_path,
        findings=findings,
        fix_summaries=fix_summaries,
        round_count=round_count,
        final_sha=final_sha,
    )


def main(out_stream: TextIO = sys.stdout, err_stream: TextIO = sys.stderr) -> int:
    """Aggregate a PR's journals, write the summary prompt, print the combined facts.

    Args:
        out_stream: Stream the result JSON is written to on success.
        err_stream: Stream error messages are written to.

    Returns:
        Exit code (0 on success, 1 on argument error).
    """
    argument_parser = argparse.ArgumentParser(
        description="Aggregate every autoconverge journal for a PR into one journal."
    )
    argument_parser.add_argument(
        "--journal", required=True, help="Path to one of the PR's wf_<runId>.json files"
    )
    argument_parser.add_argument("--pr", required=True, help="owner/repo#number")
    argument_parser.add_argument(
        "--work-dir",
        required=True,
        help="Directory the combined run tree is written under",
    )
    argument_parser.add_argument(
        "--out-prompt",
        required=True,
        help="Path the summary agent prompt is written to",
    )
    argument_parser.add_argument(
        "--standards-note", default=None, help="Deferred code-standard note, when any"
    )
    argument_parser.add_argument(
        "--copilot-note", default=None, help="Copilot gate outage note, when any"
    )
    parsed_args = argument_parser.parse_args()

    pr_arg_pattern = r"(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<number>\d+)"
    pr_match = re.fullmatch(pr_arg_pattern, parsed_args.pr)
    if pr_match is None:
        err_stream.write(
            f"Invalid --pr format: {parsed_args.pr!r}. Expected owner/repo#number.\n"
        )
        return 1
    owner = pr_match.group("owner")
    repo = pr_match.group("repo")
    pr_number = int(pr_match.group("number"))

    work_dir = Path(parsed_args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    aggregation = aggregate_pr_journals(
        Path(parsed_args.journal).resolve(), owner, repo, pr_number, work_dir
    )

    prompt = convergence_summary.build_summary_prompt(
        owner,
        repo,
        pr_number,
        aggregation.round_count,
        aggregation.findings,
        aggregation.fix_summaries,
        parsed_args.standards_note,
        parsed_args.copilot_note,
    )
    Path(parsed_args.out_prompt).write_text(prompt, encoding="utf-8")

    out_stream.write(
        json.dumps(
            {
                "combinedJournal": str(aggregation.combined_journal_path),
                "roundCount": aggregation.round_count,
                "finalSha": aggregation.final_sha,
                "findingCount": len(aggregation.findings),
            }
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
