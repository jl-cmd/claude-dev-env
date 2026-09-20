"""Constants for the baseline summary.

::

    PASS_BAND      0.20   a pass-rate gap inside it reads as no difference
    DECISIVE_DELTA 0.40   a gap at or above it reads as decisive
    TOKEN_BAND     0.15   median-token ratio that still reads as level cost
    WALL_BAND      0.20   median-wall ratio that still reads as level cost

ALL_SUMMARY_COLUMNS names the summary file's columns, and the two floors say
how high an arm has to score under each acceptance rule.
"""

from __future__ import annotations

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

DEFAULT_PASS_FLOOR = 0.60
COST_LED_PASS_FLOOR = 0.80
RATE_DIGITS = 2
TURN_DIGITS = 1
NOTE_SEPARATOR = "; "
ALL_BASELINE_ARMS = ("full-cde", "bare")
DELTA_ARM_LABEL = "delta(full-cde minus bare)"
CLEAN_EXIT_CODE = 0
