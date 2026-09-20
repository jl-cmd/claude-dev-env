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

import run_arm
from bench_parts.config.summarize_baseline_constants import (
    DECISIVE_DELTA,
    PASS_BAND,
    TOKEN_BAND,
    WALL_BAND,
)
from bench_parts.config.summarize_pilot_constants import (
    ALL_PILOT_COLUMNS,
    BARE_ARM,
    CLEAN_EXIT_CODE,
    FULL_ARM,
    KEEP_FLOOR,
    RATE_DIGITS,
    TURN_DIGITS,
)
from summarize_baseline import ArmSummary, BenchCase, BenchRow, read_rows, summarize_arm


def read_verdict(full_pass_rate: float, ablate_pass_rate: float) -> str:
    """Name the verdict the bands give for one ablation.

    ::

        full 1.0, ablate 0.2   -> KEEP          the file carries the behavior
        full 1.0, ablate 1.0   -> REMOVE        nothing measured rests on the file
        full 0.6, ablate 1.0   -> REMOVE        the install does better without it
        full 0.8, ablate 0.5   -> INCONCLUSIVE  escalate to 10 repetitions
        full 0.4, ablate 0.0   -> INCONCLUSIVE  full-cde is under the keep floor

    Args:
        full_pass_rate: The pass rate of the full-cde arm.
        ablate_pass_rate: The pass rate of the arm with the file removed.

    Returns:
        KEEP, REMOVE, or INCONCLUSIVE.
    """
    pass_delta = round(full_pass_rate - ablate_pass_rate, RATE_DIGITS)
    if abs(pass_delta) <= PASS_BAND or pass_delta <= -DECISIVE_DELTA:
        return "REMOVE"
    if pass_delta >= DECISIVE_DELTA and full_pass_rate >= KEEP_FLOOR:
        return "KEEP"
    return "INCONCLUSIVE"


def first_source_rows(
    all_row_files: list[Path], case_id: str, arm_id: str
) -> tuple[str, list[BenchRow]]:
    """Find the first row file that holds runs of one case and arm.

    Args:
        all_row_files: The row files, in the order they were given.
        case_id: The case the runs belong to.
        arm_id: The arm the runs were configured under.

    Returns:
        The name of the file that supplied the runs and those runs, or an
        empty name and an empty list when no file holds any.
    """
    for each_file in all_row_files:
        all_matches = [
            each_row
            for each_row in read_rows(each_file)
            if each_row["case"] == case_id and each_row["arm"] == arm_id
        ]
        if all_matches:
            return each_file.name, all_matches
    return "", []


def read_ablation_delta(full: ArmSummary, ablate: ArmSummary) -> ArmSummary:
    """Read the full-cde minus ablate-arm difference for one file removal.

    Args:
        full: The summary of the full-cde arm.
        ablate: The summary of the arm with the file removed.

    Returns:
        The delta row fields with the verdict, or a single ``incomplete``
        reading when either arm has no accepted run.
    """
    if full["pass_rate"] == "" or ablate["pass_rate"] == "":
        return {"reading": "incomplete", "verdict": "INCONCLUSIVE"}
    token_ratio = round(
        full["median_tokens"] / ablate["median_tokens"] - 1, RATE_DIGITS
    )
    wall_ratio = round(
        full["median_wall_seconds"] / ablate["median_wall_seconds"] - 1, RATE_DIGITS
    )
    return {
        "pass_rate": round(full["pass_rate"] - ablate["pass_rate"], RATE_DIGITS),
        "median_tokens": f"{token_ratio:+.0%}",
        "median_wall_seconds": f"{wall_ratio:+.0%}",
        "mean_turns": round(full["mean_turns"] - ablate["mean_turns"], TURN_DIGITS),
        "reading": "cost: "
        + ("inside" if abs(token_ratio) <= TOKEN_BAND else "outside")
        + " the token band, "
        + ("inside" if abs(wall_ratio) <= WALL_BAND else "outside")
        + " the wall band",
        "verdict": read_verdict(full["pass_rate"], ablate["pass_rate"]),
    }


def _pilot_arms(all_pilot_rows: list[BenchRow], case_id: str) -> list[str]:
    """List the arms the pilot file ran for one case, in first-seen order."""
    return list(
        dict.fromkeys(
            each_row["arm"]
            for each_row in all_pilot_rows
            if each_row["case"] == case_id
        )
    )


def _write_arm_rows(
    writer: csv.DictWriter[str],
    case: BenchCase,
    all_arms: list[str],
    all_row_files: list[Path],
    all_rejected: list[BenchRow],
) -> dict[str, ArmSummary]:
    """Write one summary row per arm and report the summaries by arm."""
    summary_by_arm: dict[str, ArmSummary] = {}
    for each_arm in all_arms:
        source, all_rows = first_source_rows(all_row_files, case["id"], each_arm)
        summary_by_arm[each_arm] = summarize_arm(
            case,
            all_rows,
            [
                each_row
                for each_row in all_rejected
                if each_row["case"] == case["id"] and each_row["arm"] == each_arm
            ],
        )
        writer.writerow(
            {
                "case": case["id"],
                "rule": case["acceptance"],
                "arm": each_arm,
                "source": source,
                **summary_by_arm[each_arm],
            }
        )
    return summary_by_arm


def _write_delta_rows(
    writer: csv.DictWriter[str],
    case: BenchCase,
    all_arms: list[str],
    summary_by_arm: dict[str, ArmSummary],
) -> None:
    """Write one delta row per ablate arm of a case."""
    all_ablate_arms = [
        each_arm
        for each_arm in all_arms
        if each_arm.startswith(run_arm.ABLATE_ARM_PREFIX)
    ]
    for each_arm in all_ablate_arms:
        writer.writerow(
            {
                "case": case["id"],
                "rule": case["acceptance"],
                "arm": f"delta({FULL_ARM} minus {each_arm})",
                **read_ablation_delta(
                    summary_by_arm[FULL_ARM], summary_by_arm[each_arm]
                ),
            }
        )


def _write_case_rows(
    writer: csv.DictWriter[str],
    case: BenchCase,
    all_pilot_rows: list[BenchRow],
    all_row_files: list[Path],
    all_rejected: list[BenchRow],
) -> None:
    """Write the arm rows and the delta rows of one case."""
    all_pilot_arms = _pilot_arms(all_pilot_rows, case["id"])
    if not all_pilot_arms:
        return
    all_arms = list(dict.fromkeys([FULL_ARM, BARE_ARM, *all_pilot_arms]))
    summary_by_arm = _write_arm_rows(
        writer, case, all_arms, all_row_files, all_rejected
    )
    _write_delta_rows(writer, case, all_arms, summary_by_arm)


def main() -> int:
    """Write the ablation pilot summary file and report a clean run.

    Returns:
        0 once the summary file is written.
    """
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
            _write_case_rows(
                writer, each_case, all_pilot_rows, all_row_files, all_rejected
            )
    return CLEAN_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
