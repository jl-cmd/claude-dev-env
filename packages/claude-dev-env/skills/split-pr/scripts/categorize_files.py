"""Classify changed files as hand-written or excluded churn.

::

    classify_path_churn("src/app.py")           # hand_written
    classify_path_churn("package-lock.json")    # lockfile
    classify_path_churn("vendor/lib.js")        # vendor
"""

from __future__ import annotations

from pathlib import Path

from config.split_pr_constants import (
    ALL_GENERATED_PATH_MARKERS,
    ALL_LOCKFILE_NAMES,
    ALL_MINIFIED_SUFFIXES,
    ALL_VENDOR_PATH_MARKERS,
    CHURN_CLASS_GENERATED,
    CHURN_CLASS_HAND_WRITTEN,
    CHURN_CLASS_LOCKFILE,
    CHURN_CLASS_MINIFIED,
    CHURN_CLASS_VENDOR,
    FILE_KEY_ADDITIONS,
    FILE_KEY_CHANGED_LINES,
    FILE_KEY_CHURN_CLASS,
    FILE_KEY_DELETIONS,
    FILE_KEY_PATH,
)

JsonObject = dict[str, object]


def classify_path_churn(file_path: str) -> str:
    """Return the churn class for a repository-relative path.

    Args:
        file_path: Path relative to the repository root.

    Returns:
        One of hand_written, generated, vendor, minified, or lockfile.
    """
    normalized = file_path.replace("\\", "/")
    basename = Path(normalized).name
    if basename in ALL_LOCKFILE_NAMES:
        return CHURN_CLASS_LOCKFILE
    lowered = normalized.lower()
    for each_suffix in ALL_MINIFIED_SUFFIXES:
        if lowered.endswith(each_suffix):
            return CHURN_CLASS_MINIFIED
    for each_marker in ALL_VENDOR_PATH_MARKERS:
        if each_marker.replace("\\", "/") in f"/{lowered}/" or each_marker.replace(
            "\\", "/"
        ) in lowered:
            return CHURN_CLASS_VENDOR
    for each_marker in ALL_GENERATED_PATH_MARKERS:
        marker = each_marker.replace("\\", "/")
        if marker in lowered or marker.strip("/") in lowered.split("/"):
            return CHURN_CLASS_GENERATED
    return CHURN_CLASS_HAND_WRITTEN


def annotate_files(all_file_records: list[JsonObject]) -> list[JsonObject]:
    """Annotate each file record with churn class and changed line count.

    Args:
        all_file_records: Maps with path, additions, deletions.

    Returns:
        Annotated records (new list; inputs not mutated).
    """
    all_annotated: list[JsonObject] = []
    for each_record in all_file_records:
        path = str(each_record.get(FILE_KEY_PATH, "") or "")
        additions = int(each_record.get(FILE_KEY_ADDITIONS, 0) or 0)
        deletions = int(each_record.get(FILE_KEY_DELETIONS, 0) or 0)
        changed_lines = max(0, additions) + max(0, deletions)
        all_annotated.append(
            {
                FILE_KEY_PATH: path,
                FILE_KEY_ADDITIONS: max(0, additions),
                FILE_KEY_DELETIONS: max(0, deletions),
                FILE_KEY_CHANGED_LINES: changed_lines,
                FILE_KEY_CHURN_CLASS: classify_path_churn(path),
            }
        )
    return all_annotated


def sum_churn_by_class(
    all_annotated: list[JsonObject],
    *,
    churn_class: str,
) -> int:
    """Sum changed lines for records matching ``churn_class``.

    Args:
        all_annotated: Annotated file records.
        churn_class: Target class name.

    Returns:
        Total changed lines in that class.
    """
    total = 0
    for each_record in all_annotated:
        if each_record.get(FILE_KEY_CHURN_CLASS) == churn_class:
            total += int(each_record.get(FILE_KEY_CHANGED_LINES, 0) or 0)
    return total
