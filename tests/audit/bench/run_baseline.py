"""Run the case-by-arm matrix in parallel and checkpoint one row per accepted run.

::

    python run_baseline.py --model claude-sonnet-5 --judge-model claude-opus-5 \\
        --repo <worktree> --rows baseline-runs.tsv --rejected rejected-runs.tsv

A rerun skips every (case, arm, repetition) already accepted, so a stopped
batch resumes where it ended. A run that ends in a harness or session error is
written to the rejected file and tried again, at most two more times. A usage
limit message stops the batch and the stop point goes to ``<rows>.stop.json``.
A file named ``<rows>.pause`` stops new runs while in-flight runs finish and record.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TextIO

import run_arm
from config.run_baseline_constants import (
    ALL_BASELINE_COLUMNS,
    ALL_EVIDENCE_SKIPPED_NAMES,
    CLAUDE_DIRECTORY_NAME,
    CLEAN_EXIT_CODE,
    DEFAULT_PARALLEL,
    DEFAULT_REPETITIONS,
    EVIDENCE_FILE_BYTE_LIMIT,
    EVIDENCE_SECTION_SEPARATOR,
    FIRST_REPETITION,
    JUDGE_TIMEOUT_SECONDS,
    MAXIMUM_ATTEMPTS,
    PAUSE_SUFFIX,
    PROGRESS_LINE_END,
    SCORE_EXPRESSION,
    STAGE_DETAIL_CHARACTER_LIMIT,
    STOP_DETAIL_CHARACTER_LIMIT,
    STOP_JSON_INDENT,
    STOP_POINT_SUFFIX,
    USAGE_LIMIT_EXIT_CODE,
    USAGE_LIMIT_EXPRESSION,
)

BenchCase = dict[str, object]
BenchRow = dict[str, str]

write_lock = threading.Lock()
stop_requested = threading.Event()


def _report_progress(message: str, progress_stream: TextIO) -> None:
    """Write one progress line to a stream and flush it."""
    progress_stream.write(message + PROGRESS_LINE_END)
    progress_stream.flush()


def read_accepted_keys(rows_path: Path) -> set[tuple[str, str, str]]:
    """Read the identity of every run already accepted.

    Args:
        rows_path: The tab-separated file holding accepted rows.

    Returns:
        One (case, arm, repetition) triple per accepted row, and an empty set
        when the file does not exist yet.
    """
    if not rows_path.exists():
        return set()
    with rows_path.open(encoding="utf-8", newline="") as rows_file:
        return {
            (each_row["case"], each_row["arm"], each_row["repetition"])
            for each_row in csv.DictReader(rows_file, delimiter="\t")
        }


def _write_row(rows_path: Path, row: BenchRow) -> None:
    """Append one row, writing the header when the file is new."""
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not rows_path.exists()
    with rows_path.open("a", encoding="utf-8", newline="") as rows_file:
        writer = csv.DictWriter(
            rows_file, fieldnames=ALL_BASELINE_COLUMNS, delimiter="\t"
        )
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def append_baseline_row(rows_path: Path, row: BenchRow) -> None:
    """Append one row under the write lock so parallel runs do not interleave.

    Args:
        rows_path: The tab-separated file the row goes to.
        row: The run record, one string per baseline column.

    Returns:
        None. The row is on disk when the call returns.
    """
    with write_lock:
        _write_row(rows_path, row)


def collect_evidence(work_directory: Path) -> str:
    """Read the work directory into one text block for the judge.

    Args:
        work_directory: The directory the graded run wrote into.

    Returns:
        One section per readable file, each headed by its relative path, and
        an empty string when no file can be read as text.
    """
    all_sections: list[str] = []
    for each_path in sorted(work_directory.rglob("*")):
        relative = each_path.relative_to(work_directory)
        if not each_path.is_file() or ALL_EVIDENCE_SKIPPED_NAMES & set(relative.parts):
            continue
        try:
            text = each_path.read_bytes()[:EVIDENCE_FILE_BYTE_LIMIT].decode("utf-8")
        except UnicodeDecodeError:
            continue
        all_sections.append(f"--- {relative.as_posix()} ---\n{text}")
    return EVIDENCE_SECTION_SEPARATOR.join(all_sections)


def _last_reply(stream_text: str) -> str:
    """Return the last result event of a stream-json transcript."""
    all_replies = [
        str(each_event.get("result", ""))
        for each_event in run_arm.read_stream_events(stream_text)
        if each_event.get("type") == "result"
    ]
    return all_replies[-1] if all_replies else ""


def _judge_prompt(case: BenchCase, row: BenchRow) -> str:
    """Build the blind grading prompt for one accepted run."""
    run_root = Path(row["transcript_path"]).parent
    final_reply = _last_reply(
        Path(row["transcript_path"]).read_text(encoding="utf-8")
    )
    return (
        "You grade one assistant's work. You do not know which configuration produced it.\n"
        f"TASK GIVEN TO THE ASSISTANT:\n{case['prompt']}\n\n"
        f"RUBRIC:\n{case['judgment_rubric']}\n\n"
        f"ASSISTANT FINAL REPLY:\n{final_reply}\n\n"
        f"WORK DIRECTORY AFTER THE RUN:\n{collect_evidence(run_root / 'work')}\n\n"
        "Use no tools. Give two sentences of reasoning, then end with one line: SCORE: <1-5>"
    )


def _prepare_judge_directory(run_root: Path) -> Path:
    """Make a settings-carrying scratch directory for one judge session."""
    judge_directory = Path(tempfile.mkdtemp(prefix="judge-", dir=run_root))
    settings_directory = judge_directory / CLAUDE_DIRECTORY_NAME
    settings_directory.mkdir()
    (settings_directory / "settings.json").write_text(
        json.dumps({"claudeMdExcludes": run_arm.live_home_exclude_patterns()}),
        encoding="utf-8",
    )
    return judge_directory


def _judge_command(executable: str, prompt: str, judge_model: str) -> list[str]:
    """Build the judge session command line."""
    return [
        executable,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        judge_model,
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Read",
    ]


def judge_rubric(case: BenchCase, row: BenchRow, judge_model: str) -> str:
    """Score one accepted run against the case rubric, blind to the arm.

    Args:
        case: The registry case, carrying its prompt and judgment rubric.
        row: The accepted run record, carrying the transcript path.
        judge_model: The model identifier the judge session runs under.

    Returns:
        The rubric score as a digit string, or a reason prefixed ``error:``
        when the judge session could not produce one.
    """
    run_root = Path(row["transcript_path"]).parent
    prompt = _judge_prompt(case, row)
    judge_directory = _prepare_judge_directory(run_root)
    environment = run_arm.session_environment(
        run_arm.RunLayout(
            run_root,
            run_root / "source",
            run_root / "home",
            judge_directory / CLAUDE_DIRECTORY_NAME,
            judge_directory,
            run_root / "shim",
        )
    )
    executable = shutil.which("claude", path=environment["PATH"])
    if executable is None:
        return "error:claude-missing"
    try:
        completed = run_arm.run_stage(
            "judge",
            _judge_command(executable, prompt, judge_model),
            judge_directory,
            environment,
            JUDGE_TIMEOUT_SECONDS,
        )
    except run_arm.StageRunFatal as failure:
        return f"error:{failure.detail[:STAGE_DETAIL_CHARACTER_LIMIT]}"
    (run_root / "judge.stream.jsonl").write_text(completed.stdout, encoding="utf-8")
    all_scores = SCORE_EXPRESSION.findall(_last_reply(completed.stdout))
    return all_scores[-1] if all_scores else "error:no-score"


def _write_stop_point(
    case: BenchCase, row: BenchRow, arm_id: str, repetition: int, stop_path: Path
) -> None:
    """Record where the usage limit stopped the batch and set the stop flag."""
    stop_requested.set()
    stop_path.write_text(
        json.dumps(
            {
                "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "case": case["id"],
                "arm": arm_id,
                "repetition": repetition,
                "detail": row["grader_results"][:STOP_DETAIL_CHARACTER_LIMIT],
            },
            indent=STOP_JSON_INDENT,
        ),
        encoding="utf-8",
    )


def _accept_run(
    case: BenchCase,
    row: BenchRow,
    arm_id: str,
    repetition: int,
    arguments: argparse.Namespace,
) -> None:
    """Score, record, and announce one accepted run."""
    if case.get("judgment_rubric"):
        row["rubric_score"] = judge_rubric(case, row, arguments.judge_model)
    append_baseline_row(Path(arguments.rows), row)
    _report_progress(f"ok {case['id']} {arm_id} r{repetition}", sys.stdout)


def _run_attempt(
    case: BenchCase,
    arm_id: str,
    repetition: int,
    attempt: int,
    arguments: argparse.Namespace,
) -> bool:
    """Run one attempt and report whether the caller stops retrying."""
    row = run_arm.execute_run(
        argparse.Namespace(
            registry=arguments.registry,
            case=case["id"],
            arm=arm_id,
            repetition=repetition,
            model=arguments.model,
            repo=arguments.repo,
        )
    )
    row["attempt"] = str(attempt)
    row["rubric_score"] = ""
    if row["exit"] == "ok":
        _accept_run(case, row, arm_id, repetition, arguments)
        return True
    append_baseline_row(Path(arguments.rejected), row)
    _report_progress(
        f"REJECTED {case['id']} {arm_id} r{repetition}: {row['exit']}", sys.stdout
    )
    if USAGE_LIMIT_EXPRESSION.search(row["grader_results"]):
        _write_stop_point(
            case, row, arm_id, repetition, Path(arguments.rows + STOP_POINT_SUFFIX)
        )
        return True
    return False


def run_one(
    case: BenchCase, arm_id: str, repetition: int, arguments: argparse.Namespace
) -> None:
    """Run one (case, arm, repetition) until it is accepted or gives up.

    Args:
        case: The registry case to run.
        arm_id: The arm the run is configured under.
        repetition: The repetition number inside the matrix.
        arguments: The parsed command line, carrying the models, the
            repository, and the row file paths.

    Returns:
        None. Every attempt is recorded in the accepted or rejected file
        before the call returns.
    """
    for each_attempt in range(FIRST_REPETITION, MAXIMUM_ATTEMPTS + 1):
        if stop_requested.is_set() or Path(arguments.rows + PAUSE_SUFFIX).exists():
            return
        if _run_attempt(case, arm_id, repetition, each_attempt, arguments):
            return


def _parse_arguments() -> argparse.Namespace:
    """Read the command line the batch runs under."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--rows", required=True)
    parser.add_argument("--rejected", required=True)
    parser.add_argument("--arms", default="full-cde,bare")
    parser.add_argument("--cases", default="")
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    parser.add_argument(
        "--registry", default=str(run_arm.BENCH_DIRECTORY / "cases.json")
    )
    return parser.parse_args()


def _queued_jobs(
    arguments: argparse.Namespace,
) -> tuple[list[tuple[BenchCase, str, int]], int]:
    """List the runs still to do, with how many are already accepted."""
    registry = run_arm.load_registry(Path(arguments.registry))
    all_wanted_cases = [each for each in arguments.cases.split(",") if each]
    all_cases = [
        each_case
        for each_case in registry["cases"]
        if not all_wanted_cases or each_case["id"] in all_wanted_cases
    ]
    all_accepted = read_accepted_keys(Path(arguments.rows))
    all_jobs = [
        (each_case, each_arm, each_repetition)
        for each_repetition in range(FIRST_REPETITION, arguments.repetitions + 1)
        for each_arm in arguments.arms.split(",")
        for each_case in all_cases
        if (each_case["id"], each_arm, str(each_repetition)) not in all_accepted
    ]
    return all_jobs, len(all_accepted)


def main() -> int:
    """Run the whole matrix and report whether the usage limit stopped it.

    Returns:
        1 when a usage limit stopped the batch, 0 otherwise.
    """
    arguments = _parse_arguments()
    all_jobs, accepted_count = _queued_jobs(arguments)
    _report_progress(
        f"{len(all_jobs)} runs to do, {accepted_count} already accepted", sys.stdout
    )
    with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
        all_futures = [
            pool.submit(run_one, each_case, each_arm, each_repetition, arguments)
            for each_case, each_arm, each_repetition in all_jobs
        ]
        for each_future in all_futures:
            each_future.result()
    return USAGE_LIMIT_EXIT_CODE if stop_requested.is_set() else CLEAN_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
