"""Constants for the ablation pilot summary.

::

    KEEP_FLOOR 0.60   full-cde scores at least this before a KEEP verdict
    FULL_ARM          the arm every ablate arm is measured against

ALL_PILOT_COLUMNS adds the source file and the verdict to the baseline summary
columns.
"""

from __future__ import annotations

from bench_parts.config.summarize_baseline_constants import ALL_SUMMARY_COLUMNS

ALL_PILOT_COLUMNS = (*ALL_SUMMARY_COLUMNS, "source", "verdict")
KEEP_FLOOR = 0.60
FULL_ARM = "full-cde"
BARE_ARM = "bare"
RATE_DIGITS = 2
TURN_DIGITS = 1
CLEAN_EXIT_CODE = 0
