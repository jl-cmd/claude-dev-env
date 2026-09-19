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
import re
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import run_arm

ALL_BASELINE_COLUMNS = (*run_arm.ALL_ROW_COLUMNS, "rubric_score", "attempt")
MAXIMUM_ATTEMPTS = 3
USAGE_LIMIT_EXPRESSION = re.compile(
    r"usage limit|limit reached|rate.?limit|\b429\b|out of extra usage", re.IGNORECASE
)
SCORE_EXPRESSION = re.compile(r"SCORE:\s*([1-5])\b")
ALL_EVIDENCE_SKIPPED_NAMES = {
    ".claude",
    ".agents",
    ".git",
    "__pycache__",
    ".pytest_cache",
}
EVIDENCE_FILE_BYTE_LIMIT = 20000
JUDGE_TIMEOUT_SECONDS = 600

write_lock = threading.Lock()
stop_requested = threading.Event()


def read_accepted_keys(rows_path: Path) -> set[tuple[str, str, str]]:
    if not rows_path.exists():
        return set()
    with rows_path.open(encoding="utf-8", newline="") as rows_file:
        return {
            (each_row["case"], each_row["arm"], each_row["repetition"])
            for each_row in csv.DictReader(rows_file, delimiter="\t")
        }


def append_baseline_row(rows_path: Path, row: dict[str, str]) -> None:
    with write_lock:
        rows_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not rows_path.exists()
        with rows_path.open("a", encoding="utf-8", newline="") as rows_file:
            writer = csv.DictWriter(
                rows_file, fieldnames=ALL_BASELINE_COLUMNS, delimiter="\t"
            )
            if is_new:
                writer.writeheader()
            writer.writerow(row)


def collect_evidence(work_directory: Path) -> str:
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
    return "\n".join(all_sections)


def judge_rubric(case: dict[str, Any], row: dict[str, str], judge_model: str) -> str:
    """Score one accepted run against the case rubric, blind to the arm."""
    run_root = Path(row["transcript_path"]).parent
    all_events = run_arm.read_stream_events(
        Path(row["transcript_path"]).read_text(encoding="utf-8")
    )
    all_replies = [
        str(each_event.get("result", ""))
        for each_event in all_events
        if each_event.get("type") == "result"
    ]
    prompt = (
        "You grade one assistant's work. You do not know which configuration produced it.\n"
        f"TASK GIVEN TO THE ASSISTANT:\n{case['prompt']}\n\n"
        f"RUBRIC:\n{case['judgment_rubric']}\n\n"
        f"ASSISTANT FINAL REPLY:\n{all_replies[-1] if all_replies else ''}\n\n"
        f"WORK DIRECTORY AFTER THE RUN:\n{collect_evidence(run_root / 'work')}\n\n"
        "Use no tools. Give two sentences of reasoning, then end with one line: SCORE: <1-5>"
    )
    judge_directory = Path(tempfile.mkdtemp(prefix="judge-", dir=run_root))
    (judge_directory / ".claude").mkdir()
    (judge_directory / ".claude" / "settings.json").write_text(
        json.dumps({"claudeMdExcludes": run_arm.live_home_exclude_patterns()}),
        encoding="utf-8",
    )
    environment = run_arm.session_environment(
        run_arm.RunLayout(
            run_root,
            run_root / "source",
            run_root / "home",
            judge_directory / ".claude",
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
            [
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
            ],
            judge_directory,
            environment,
            JUDGE_TIMEOUT_SECONDS,
        )
    except run_arm.StageRunFatal as failure:
        return f"error:{failure.detail[:80]}"
    (run_root / "judge.stream.jsonl").write_text(completed.stdout, encoding="utf-8")
    all_judge_replies = [
        str(each_event.get("result", ""))
        for each_event in run_arm.read_stream_events(completed.stdout)
        if each_event.get("type") == "result"
    ]
    all_scores = SCORE_EXPRESSION.findall(
        all_judge_replies[-1] if all_judge_replies else ""
    )
    return all_scores[-1] if all_scores else "error:no-score"


def run_one(
    case: dict[str, Any], arm_id: str, repetition: int, arguments: argparse.Namespace
) -> None:
    for each_attempt in range(1, MAXIMUM_ATTEMPTS + 1):
        if stop_requested.is_set() or Path(arguments.rows + ".pause").exists():
            return
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
        row["attempt"] = str(each_attempt)
        row["rubric_score"] = ""
        if row["exit"] == "ok":
            if case.get("judgment_rubric"):
                row["rubric_score"] = judge_rubric(case, row, arguments.judge_model)
            append_baseline_row(Path(arguments.rows), row)
            print(f"ok {case['id']} {arm_id} r{repetition}", flush=True)
            return
        append_baseline_row(Path(arguments.rejected), row)
        print(
            f"REJECTED {case['id']} {arm_id} r{repetition}: {row['exit']}", flush=True
        )
        if USAGE_LIMIT_EXPRESSION.search(row["grader_results"]):
            stop_requested.set()
            Path(arguments.rows + ".stop.json").write_text(
                json.dumps(
                    {
                        "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "case": case["id"],
                        "arm": arm_id,
                        "repetition": repetition,
                        "detail": row["grader_results"][:400],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--rows", required=True)
    parser.add_argument("--rejected", required=True)
    parser.add_argument("--arms", default="full-cde,bare")
    parser.add_argument("--cases", default="")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument(
        "--registry", default=str(run_arm.BENCH_DIRECTORY / "cases.json")
    )
    arguments = parser.parse_args()
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
        for each_repetition in range(1, arguments.repetitions + 1)
        for each_arm in arguments.arms.split(",")
        for each_case in all_cases
        if (each_case["id"], each_arm, str(each_repetition)) not in all_accepted
    ]
    print(
        f"{len(all_jobs)} runs to do, {len(all_accepted)} already accepted", flush=True
    )
    with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
        all_futures = [
            pool.submit(run_one, each_case, each_arm, each_repetition, arguments)
            for each_case, each_arm, each_repetition in all_jobs
        ]
        for each_future in all_futures:
            each_future.result()
    return 1 if stop_requested.is_set() else 0


if __name__ == "__main__":
    sys.exit(main())
