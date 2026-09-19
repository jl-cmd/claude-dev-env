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
from typing import Any

import run_arm

ALL_SUMMARY_COLUMNS = (
    "case",
    "rule",
    "arm",
    "accepted_runs",
    "pass_rate",
    "grader_pass_rates",
    "mean_rubric",
    "mean_turns",
    "mean_tokens",
    "median_tokens",
    "mean_wall_seconds",
    "median_wall_seconds",
    "total_denials",
    "harness_errors",
    "session_errors",
    "reading",
)
PASS_BAND = 0.20
DECISIVE_DELTA = 0.40
TOKEN_BAND = 0.15
WALL_BAND = 0.20


def read_rows(rows_path: Path) -> list[dict[str, str]]:
    if not rows_path.exists():
        return []
    with rows_path.open(encoding="utf-8", newline="") as rows_file:
        return list(csv.DictReader(rows_file, delimiter="\t"))


def summarize_arm(
    case: dict[str, Any],
    all_rows: list[dict[str, str]],
    all_rejected: list[dict[str, str]],
) -> dict[str, Any]:
    all_primary = list(case["primary_graders"])
    all_results = [json.loads(each_row["grader_results"]) for each_row in all_rows]
    all_grader_ids = sorted({each_id for each in all_results for each_id in each})
    all_passes = [
        all(each.get(each_id, ["error"])[0] == "pass" for each_id in all_primary)
        for each in all_results
    ]
    all_scores = [
        int(each_row["rubric_score"])
        for each_row in all_rows
        if each_row.get("rubric_score", "").isdigit()
    ]
    all_tokens = [int(each_row["tokens"]) for each_row in all_rows]
    all_walls = [float(each_row["wall_seconds"]) for each_row in all_rows]
    return {
        "accepted_runs": len(all_rows),
        "pass_rate": round(sum(all_passes) / len(all_rows), 2) if all_rows else "",
        "grader_pass_rates": json.dumps(
            {
                each_id: round(
                    sum(
                        each.get(each_id, ["error"])[0] == "pass"
                        for each in all_results
                    )
                    / len(all_results),
                    2,
                )
                for each_id in all_grader_ids
            },
            sort_keys=True,
        ),
        "mean_rubric": round(statistics.mean(all_scores), 2) if all_scores else "",
        "mean_turns": round(
            statistics.mean(int(each_row["turns"]) for each_row in all_rows), 1
        )
        if all_rows
        else "",
        "mean_tokens": round(statistics.mean(all_tokens)) if all_rows else "",
        "median_tokens": round(statistics.median(all_tokens)) if all_rows else "",
        "mean_wall_seconds": round(statistics.mean(all_walls), 1) if all_rows else "",
        "median_wall_seconds": round(statistics.median(all_walls), 1)
        if all_rows
        else "",
        "total_denials": sum(
            int(each_row["permission_denials"] or 0) for each_row in all_rows
        ),
        "harness_errors": sum(
            each_row["exit"].startswith("harness_error") for each_row in all_rejected
        ),
        "session_errors": sum(
            each_row["exit"].startswith("session_error") for each_row in all_rejected
        ),
    }


def read_delta(
    case: dict[str, Any], full: dict[str, Any], bare: dict[str, Any]
) -> dict[str, Any]:
    if full["pass_rate"] == "" or bare["pass_rate"] == "":
        return {"reading": "incomplete"}
    pass_delta = round(full["pass_rate"] - bare["pass_rate"], 2)
    token_ratio = round(full["median_tokens"] / bare["median_tokens"] - 1, 2)
    wall_ratio = round(full["median_wall_seconds"] / bare["median_wall_seconds"] - 1, 2)
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
    if case["acceptance"] == "default" and full["pass_rate"] < 0.60:
        all_notes.append("full-cde below the 0.60 floor")
    if (
        case["acceptance"] == "cost-led"
        and min(full["pass_rate"], bare["pass_rate"]) < 0.80
    ):
        all_notes.append("an arm is below the 0.80 floor")
    all_notes.append(
        "cost: "
        + ("inside" if abs(token_ratio) <= TOKEN_BAND else "outside")
        + " the token band, "
        + ("inside" if abs(wall_ratio) <= WALL_BAND else "outside")
        + " the wall band"
    )
    rubric_delta = (
        round(full["mean_rubric"] - bare["mean_rubric"], 2)
        if full["mean_rubric"] != "" and bare["mean_rubric"] != ""
        else ""
    )
    return {
        "pass_rate": pass_delta,
        "mean_rubric": rubric_delta,
        "median_tokens": f"{token_ratio:+.0%}",
        "median_wall_seconds": f"{wall_ratio:+.0%}",
        "mean_turns": round(full["mean_turns"] - bare["mean_turns"], 1),
        "reading": "; ".join(all_notes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", required=True)
    parser.add_argument("--rejected", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument(
        "--registry", default=str(run_arm.BENCH_DIRECTORY / "cases.json")
    )
    arguments = parser.parse_args()
    registry = run_arm.load_registry(Path(arguments.registry))
    rows_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    rejected_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for each_row in read_rows(Path(arguments.rows)):
        rows_by_key[(each_row["case"], each_row["arm"])].append(each_row)
    for each_row in read_rows(Path(arguments.rejected)):
        rejected_by_key[(each_row["case"], each_row["arm"])].append(each_row)
    with Path(arguments.summary).open(
        "w", encoding="utf-8", newline=""
    ) as summary_file:
        writer = csv.DictWriter(
            summary_file, fieldnames=ALL_SUMMARY_COLUMNS, delimiter="\t"
        )
        writer.writeheader()
        for each_case in registry["cases"]:
            by_arm = {
                each_arm: summarize_arm(
                    each_case,
                    rows_by_key[(each_case["id"], each_arm)],
                    rejected_by_key[(each_case["id"], each_arm)],
                )
                for each_arm in ("full-cde", "bare")
            }
            for each_arm, each_summary in by_arm.items():
                writer.writerow(
                    {
                        "case": each_case["id"],
                        "rule": each_case["acceptance"],
                        "arm": each_arm,
                        **each_summary,
                    }
                )
            writer.writerow(
                {
                    "case": each_case["id"],
                    "rule": each_case["acceptance"],
                    "arm": "delta(full-cde minus bare)",
                    **read_delta(each_case, by_arm["full-cde"], by_arm["bare"]),
                }
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
