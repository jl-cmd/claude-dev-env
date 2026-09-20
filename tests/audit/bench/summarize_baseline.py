"""Fold accepted baseline rows into one summary row per case and arm.

::

    python summarize_baseline.py --rows baseline-runs.tsv --rejected rejected-runs.tsv \\
        --summary baseline-summary.tsv

Each case also gets a ``delta`` row: full-cde minus bare, read against the
bands declared in ``cases.json``. A case whose two arms both score 0 or both
score 1 is marked weak, because its graders separate nothing.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import run_arm
from bench_parts.config.summarize_baseline_constants import (
    ALL_BASELINE_ARMS,
    ALL_SUMMARY_COLUMNS,
    CLEAN_EXIT_CODE,
    COST_LED_PASS_FLOOR,
    DECISIVE_DELTA,
    DEFAULT_PASS_FLOOR,
    DELTA_ARM_LABEL,
    NOTE_SEPARATOR,
    PASS_BAND,
    RATE_DIGITS,
    TURN_DIGITS,
    WALL_BAND,
    TOKEN_BAND,
)

BenchCase = dict[str, object]
BenchRow = dict[str, str]
GraderMap = dict[str, list[str]]
ArmSummary = dict[str, float | int | str]


def read_rows(rows_path: Path) -> list[BenchRow]:
    """Read one run record per line of a tab-separated row file.

    Args:
        rows_path: The row file to read.

    Returns:
        One record per row, and an empty list when the file does not exist.
    """
    if not rows_path.exists():
        return []
    with rows_path.open(encoding="utf-8", newline="") as rows_file:
        return list(csv.DictReader(rows_file, delimiter="\t"))


def _grader_pass_rates(all_grader_maps: list[GraderMap]) -> str:
    """Report the pass rate of each grader as sorted JSON."""
    all_grader_ids = sorted(
        {each_id for each_map in all_grader_maps for each_id in each_map}
    )
    return json.dumps(
        {
            each_id: round(
                sum(
                    each_map.get(each_id, ["error"])[0] == "pass"
                    for each_map in all_grader_maps
                )
                / len(all_grader_maps),
                RATE_DIGITS,
            )
            for each_id in all_grader_ids
        },
        sort_keys=True,
    )


def _error_counts(all_rejected: list[BenchRow]) -> ArmSummary:
    """Count the harness and session errors among rejected runs."""
    return {
        "harness_errors": sum(
            each_row["exit"].startswith("harness_error") for each_row in all_rejected
        ),
        "session_errors": sum(
            each_row["exit"].startswith("session_error") for each_row in all_rejected
        ),
    }


def _central_readings(all_rows: list[BenchRow]) -> ArmSummary:
    """Report the mean and median cost readings over accepted runs."""
    all_scores = [
        int(each_row["rubric_score"])
        for each_row in all_rows
        if each_row.get("rubric_score", "").isdigit()
    ]
    all_tokens = [int(each_row["tokens"]) for each_row in all_rows]
    all_walls = [float(each_row["wall_seconds"]) for each_row in all_rows]
    return {
        "mean_rubric": round(statistics.mean(all_scores), RATE_DIGITS)
        if all_scores
        else "",
        "mean_turns": round(
            statistics.mean(int(each_row["turns"]) for each_row in all_rows),
            TURN_DIGITS,
        )
        if all_rows
        else "",
        "mean_tokens": round(statistics.mean(all_tokens)) if all_rows else "",
        "median_tokens": round(statistics.median(all_tokens)) if all_rows else "",
        "mean_wall_seconds": round(statistics.mean(all_walls), TURN_DIGITS)
        if all_rows
        else "",
        "median_wall_seconds": round(statistics.median(all_walls), TURN_DIGITS)
        if all_rows
        else "",
    }


def summarize_arm(
    case: BenchCase,
    all_rows: list[BenchRow],
    all_rejected: list[BenchRow],
) -> ArmSummary:
    """Fold every accepted run of one case and arm into one summary row.

    Args:
        case: The registry case, carrying the primary grader identifiers.
        all_rows: The accepted runs of this case and arm.
        all_rejected: The rejected runs of this case and arm.

    Returns:
        One field per summary column the arm rows carry, with an empty string
        wherever no accepted run supports a reading.
    """
    all_primary = list(case["primary_graders"])
    all_grader_maps = [json.loads(each_row["grader_results"]) for each_row in all_rows]
    all_passes = [
        all(each_map.get(each_id, ["error"])[0] == "pass" for each_id in all_primary)
        for each_map in all_grader_maps
    ]
    return {
        "accepted_runs": len(all_rows),
        "pass_rate": round(sum(all_passes) / len(all_rows), RATE_DIGITS)
        if all_rows
        else "",
        "grader_pass_rates": _grader_pass_rates(all_grader_maps),
        **_central_readings(all_rows),
        "total_denials": sum(
            int(each_row["permission_denials"] or 0) for each_row in all_rows
        ),
        **_error_counts(all_rejected),
    }


def _quality_notes(case: BenchCase, full: ArmSummary, bare: ArmSummary) -> list[str]:
    """Read the pass-rate gap of one case against the declared bands."""
    pass_delta = round(full["pass_rate"] - bare["pass_rate"], RATE_DIGITS)
    all_notes: list[str] = []
    if abs(pass_delta) <= PASS_BAND:
        all_notes.append("quality: inside the band")
    elif abs(pass_delta) >= DECISIVE_DELTA:
        all_notes.append(
            "quality: decisive for " + ("full-cde" if pass_delta > 0 else "bare")
        )
    else:
        all_notes.append("quality: between band and decisive, escalate to 10")
    if full["pass_rate"] == bare["pass_rate"] and full["pass_rate"] in (0, 1):
        all_notes.append("WEAK CASE: both arms at " + str(full["pass_rate"]))
    if case["acceptance"] == "default" and full["pass_rate"] < DEFAULT_PASS_FLOOR:
        all_notes.append("full-cde below the 0.60 floor")
    if (
        case["acceptance"] == "cost-led"
        and min(full["pass_rate"], bare["pass_rate"]) < COST_LED_PASS_FLOOR
    ):
        all_notes.append("an arm is below the 0.80 floor")
    return all_notes


def _cost_note(token_ratio: float, wall_ratio: float) -> str:
    """Read the token and wall ratios against their bands."""
    return (
        "cost: "
        + ("inside" if abs(token_ratio) <= TOKEN_BAND else "outside")
        + " the token band, "
        + ("inside" if abs(wall_ratio) <= WALL_BAND else "outside")
        + " the wall band"
    )


def read_delta(case: BenchCase, full: ArmSummary, bare: ArmSummary) -> ArmSummary:
    """Read the full-cde minus bare difference for one case.

    Args:
        case: The registry case, carrying its acceptance rule.
        full: The summary of the full-cde arm.
        bare: The summary of the bare arm.

    Returns:
        The delta row fields, or a single ``incomplete`` reading when either
        arm has no accepted run.
    """
    if full["pass_rate"] == "" or bare["pass_rate"] == "":
        return {"reading": "incomplete"}
    token_ratio = round(full["median_tokens"] / bare["median_tokens"] - 1, RATE_DIGITS)
    wall_ratio = round(
        full["median_wall_seconds"] / bare["median_wall_seconds"] - 1, RATE_DIGITS
    )
    all_notes = _quality_notes(case, full, bare)
    all_notes.append(_cost_note(token_ratio, wall_ratio))
    rubric_delta = (
        round(full["mean_rubric"] - bare["mean_rubric"], RATE_DIGITS)
        if full["mean_rubric"] != "" and bare["mean_rubric"] != ""
        else ""
    )
    return {
        "pass_rate": round(full["pass_rate"] - bare["pass_rate"], RATE_DIGITS),
        "mean_rubric": rubric_delta,
        "median_tokens": f"{token_ratio:+.0%}",
        "median_wall_seconds": f"{wall_ratio:+.0%}",
        "mean_turns": round(full["mean_turns"] - bare["mean_turns"], TURN_DIGITS),
        "reading": NOTE_SEPARATOR.join(all_notes),
    }


def _write_case_rows(
    writer: csv.DictWriter[str],
    case: BenchCase,
    rows_by_key: dict[tuple[str, str], list[BenchRow]],
    rejected_by_key: dict[tuple[str, str], list[BenchRow]],
) -> None:
    """Write one arm row per baseline arm, then the delta row for one case."""
    by_arm = {
        each_arm: summarize_arm(
            case,
            rows_by_key[(case["id"], each_arm)],
            rejected_by_key[(case["id"], each_arm)],
        )
        for each_arm in ALL_BASELINE_ARMS
    }
    for each_arm, each_summary in by_arm.items():
        writer.writerow(
            {
                "case": case["id"],
                "rule": case["acceptance"],
                "arm": each_arm,
                **each_summary,
            }
        )
    writer.writerow(
        {
            "case": case["id"],
            "rule": case["acceptance"],
            "arm": DELTA_ARM_LABEL,
            **read_delta(case, by_arm["full-cde"], by_arm["bare"]),
        }
    )


def _rows_by_case_and_arm(
    rows_path: Path,
) -> dict[tuple[str, str], list[BenchRow]]:
    """Group the rows of one file by their case and arm."""
    grouped: dict[tuple[str, str], list[BenchRow]] = defaultdict(list)
    for each_row in read_rows(rows_path):
        grouped[(each_row["case"], each_row["arm"])].append(each_row)
    return grouped


def main() -> int:
    """Write the baseline summary file and report a clean run.

    Returns:
        0 once the summary file is written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", required=True)
    parser.add_argument("--rejected", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument(
        "--registry", default=str(run_arm.BENCH_DIRECTORY / "cases.json")
    )
    arguments = parser.parse_args()
    registry = run_arm.load_registry(Path(arguments.registry))
    rows_by_key = _rows_by_case_and_arm(Path(arguments.rows))
    rejected_by_key = _rows_by_case_and_arm(Path(arguments.rejected))
    with Path(arguments.summary).open(
        "w", encoding="utf-8", newline=""
    ) as summary_file:
        writer = csv.DictWriter(
            summary_file, fieldnames=ALL_SUMMARY_COLUMNS, delimiter="\t"
        )
        writer.writeheader()
        for each_case in registry["cases"]:
            _write_case_rows(writer, each_case, rows_by_key, rejected_by_key)
    return CLEAN_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
