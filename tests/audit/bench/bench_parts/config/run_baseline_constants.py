"""Constants for the baseline matrix runner.

::

    MAXIMUM_ATTEMPTS = 3          one run, then at most two retries
    EVIDENCE_FILE_BYTE_LIMIT      how much of one file the judge sees
    <rows>.pause                  PAUSE_SUFFIX, holds new runs back
    <rows>.stop.json              STOP_POINT_SUFFIX, where a usage limit stopped

USAGE_LIMIT_EXPRESSION matches the grader text that stops the batch, and
SCORE_EXPRESSION reads the rubric score out of the judge reply.
"""

from __future__ import annotations

import re

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

EVIDENCE_SECTION_SEPARATOR = "\n"
PROGRESS_LINE_END = "\n"
CLAUDE_DIRECTORY_NAME = ".claude"
PAUSE_SUFFIX = ".pause"
STOP_POINT_SUFFIX = ".stop.json"
STAGE_DETAIL_CHARACTER_LIMIT = 80
STOP_DETAIL_CHARACTER_LIMIT = 400
STOP_JSON_INDENT = 2
DEFAULT_REPETITIONS = 5
DEFAULT_PARALLEL = 3
USAGE_LIMIT_EXIT_CODE = 1
CLEAN_EXIT_CODE = 0
FIRST_REPETITION = 1
