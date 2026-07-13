"""Freshness check for the candidate test files the gate resolves.

A candidate satisfies the gate when it was modified inside the freshness window
and holds a real test function, so a stale test or a same-named file with no
test evidence does not open the gate.
"""

import re
import time
from pathlib import Path

from tdd_enforcer_parts.config.tdd_enforcer_constants import FRESHNESS_WINDOW_SECONDS


def _freshness_seconds() -> int:
    return FRESHNESS_WINDOW_SECONDS


def _test_file_encoding() -> str:
    return "utf-8"


def _test_function_patterns() -> tuple[re.Pattern[str], ...]:
    return (
        re.compile(r"\bdef\s+test_"),
        re.compile(r"\b(?:it|test|describe)\s*\("),
    )


def _safe_mtime(candidate_path: Path) -> float | None:
    try:
        return candidate_path.stat().st_mtime
    except (FileNotFoundError, OSError):
        return None


def _read_candidate_text(candidate_path: Path) -> str | None:
    try:
        with candidate_path.open("r", encoding=_test_file_encoding(), errors="ignore") as each_file:
            return each_file.read()
    except (FileNotFoundError, OSError):
        return None


def _contains_test_evidence(candidate_path: Path) -> bool:
    test_file_content = _read_candidate_text(candidate_path)
    if test_file_content is None:
        return False
    return any(
        each_pattern.search(test_file_content) for each_pattern in _test_function_patterns()
    )


def _candidate_is_fresh_test(
    candidate_path: Path, current_time: float, freshness_seconds: int
) -> bool:
    candidate_mtime = _safe_mtime(candidate_path)
    if candidate_mtime is None:
        return False
    if current_time - candidate_mtime > freshness_seconds:
        return False
    return _contains_test_evidence(candidate_path)


def has_fresh_test(all_candidates: list[Path], freshness_seconds: int) -> bool:
    """Return whether any candidate is a recently modified real test file.

    Args:
        all_candidates: Candidate test paths for the production file.
        freshness_seconds: Maximum age, in seconds, a test may have.

    Returns:
        True when at least one candidate was modified within the window and
        holds a test function.
    """
    current_time = time.time()
    return any(
        _candidate_is_fresh_test(each_candidate, current_time, freshness_seconds)
        for each_candidate in all_candidates
    )
