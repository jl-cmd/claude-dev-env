"""Fold ablation pilot rows into one summary row per case and arm, with a verdict.

::

    python summarize_pilot.py --rows pilot-ablation-runs.tsv baseline-refresh-runs.tsv \\
        baseline-runs.tsv --rejected pilot-rejected-runs.tsv --summary pilot-ablation-summary.tsv

Row files are read in the order given. For one case and arm, the first file
that holds rows for it supplies all of them, so a refresh row outranks the
older baseline row. Each ablate arm gets a ``delta`` row: full-cde minus the
ablate arm.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import run_arm
from summarize_baseline import (
    ALL_SUMMARY_COLUMNS,
    DECISIVE_DELTA,
    PASS_BAND,
    TOKEN_BAND,
    WALL_BAND,
    read_rows,
    summarize_arm,
)

ALL_PILOT_COLUMNS = (*ALL_SUMMARY_COLUMNS, "source", "verdict")
KEEP_FLOOR = 0.60
FULL_ARM = "full-cde"


def read_verdict(full_pass_rate: float, ablate_pass_rate: float) -> str:
    """Name the verdict the bands give for one ablation.

    ::

        full 1.0, ablate 0.2   -> KEEP          the file carries the behavior
        full 1.0, ablate 1.0   -> REMOVE        nothing measured rests on the file
        full 0.6, ablate 1.0   -> REMOVE        the install does better without it
        full 0.8, ablate 0.5   -> INCONCLUSIVE  escalate to 10 repetitions
        full 0.4, ablate 0.0   -> INCONCLUSIVE  full-cde is under the keep floor
    """
    pass_delta = round(full_pass_rate - ablate_pass_rate, 2)
    if abs(pass_delta) <= PASS_BAND or pass_delta <= -DECISIVE_DELTA:
        return "REMOVE"
    if pass_delta >= DECISIVE_DELTA and full_pass_rate >= KEEP_FLOOR:
        return "KEEP"
    return "INCONCLUSIVE"


def first_source_rows(
    all_row_files: list[Path], case_id: str, arm_id: str
) -> tuple[str, list[dict[str, str]]]:
    for each_file in all_row_files:
        all_matches = [
            each_row
            for each_row in read_rows(each_file)
            if each_row["case"] == case_id and each_row["arm"] == arm_id
        ]
        if all_matches:
            return each_file.name, all_matches
    return "", []


def read_ablation_delta(full: dict[str, Any], ablate: dict[str, Any]) -> dict[str, Any]:
    if full["pass_rate"] == "" or ablate["pass_rate"] == "":
        return {"reading": "incomplete", "verdict": "INCONCLUSIVE"}
    token_ratio = round(full["median_tokens"] / ablate["median_tokens"] - 1, 2)
    wall_ratio = round(
        full["median_wall_seconds"] / ablate["median_wall_seconds"] - 1, 2
    )
    return {
        "pass_rate": round(full["pass_rate"] - ablate["pass_rate"], 2),
        "median_tokens": f"{token_ratio:+.0%}",
        "median_wall_seconds": f"{wall_ratio:+.0%}",
        "mean_turns": round(full["mean_turns"] - ablate["mean_turns"], 1),
        "reading": "cost: "
        + ("inside" if abs(token_ratio) <= TOKEN_BAND else "outside")
        + " the token band, "
        + ("inside" if abs(wall_ratio) <= WALL_BAND else "outside")
        + " the wall band",
        "verdict": read_verdict(full["pass_rate"], ablate["pass_rate"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", required=True, nargs="+")
    parser.add_argument("--rejected", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument(
        "--registry", default=str(run_arm.BENCH_DIRECTORY / "cases.json")
    )
    arguments = parser.parse_args()
    registry = run_arm.load_registry(Path(arguments.registry))
    all_row_files = [Path(each_path) for each_path in arguments.rows]
    all_pilot_rows = read_rows(all_row_files[0])
    all_rejected = read_rows(Path(arguments.rejected))
    with Path(arguments.summary).open(
        "w", encoding="utf-8", newline=""
    ) as summary_file:
        writer = csv.DictWriter(
            summary_file, fieldnames=ALL_PILOT_COLUMNS, delimiter="\t"
        )
        writer.writeheader()
        for each_case in registry["cases"]:
            all_pilot_arms = list(
                dict.fromkeys(
                    each_row["arm"]
                    for each_row in all_pilot_rows
                    if each_row["case"] == each_case["id"]
                )
            )
            if not all_pilot_arms:
                continue
            all_arms = list(dict.fromkeys([FULL_ARM, "bare", *all_pilot_arms]))
            summary_by_arm: dict[str, dict[str, Any]] = {}
            for each_arm in all_arms:
                source, all_rows = first_source_rows(
                    all_row_files, each_case["id"], each_arm
                )
                summary_by_arm[each_arm] = summarize_arm(
                    each_case,
                    all_rows,
                    [
                        each_row
                        for each_row in all_rejected
                        if each_row["case"] == each_case["id"]
                        and each_row["arm"] == each_arm
                    ],
                )
                writer.writerow(
                    {
                        "case": each_case["id"],
                        "rule": each_case["acceptance"],
                        "arm": each_arm,
                        "source": source,
                        **summary_by_arm[each_arm],
                    }
                )
            for each_arm in all_arms:
                if each_arm.startswith(run_arm.ABLATE_ARM_PREFIX):
                    writer.writerow(
                        {
                            "case": each_case["id"],
                            "rule": each_case["acceptance"],
                            "arm": f"delta({FULL_ARM} minus {each_arm})",
                            **read_ablation_delta(
                                summary_by_arm[FULL_ARM], summary_by_arm[each_arm]
                            ),
                        }
                    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
