"""Scope proposed violations into newly-introduced versus pre-existing."""

from collections import Counter
from typing import List

from .config import IDENTITY_KEY_LENGTH
from .file_content_io import _read_target_file_content
from .file_scoped_runners import validate_proposed_file
from .validator_result import ValidatorResult
from .violation_parsing import (
    ViolationIdentity,
    _enclosing_function_name_by_line,
    _failed_results,
    _line_identity,
    _located_violation_lines,
    _violation_identities,
)


def _baseline_violation_identities(file_path: str) -> Counter[ViolationIdentity]:
    """Return the violation identity counts the on-disk file already carries.

    Args:
        file_path: The write's target path, read as the pre-edit baseline.

    Returns:
        The baseline identity multiset, empty when the file is absent or empty.
    """
    baseline_content = _read_target_file_content(file_path)
    if not baseline_content:
        return Counter()
    baseline_failed = _failed_results(validate_proposed_file(file_path, baseline_content))
    return _violation_identities(baseline_failed, baseline_content)


def _identity_key_counts(
    baseline_identities: Counter[ViolationIdentity],
) -> Counter[tuple[str, str]]:
    """Sum baseline counts down to ``(validator, enclosing function)`` keys.

    Args:
        baseline_identities: The baseline identity multiset.

    Returns:
        The per-key line counts with messages ignored, so a violation whose
        message drifted with the edit still finds its baseline budget.
    """
    key_counts: Counter[tuple[str, str]] = Counter()
    for each_identity, each_count in baseline_identities.items():
        key_counts[each_identity[:IDENTITY_KEY_LENGTH]] += each_count
    return key_counts


def _result_with_output(
    source_result: ValidatorResult, all_output_lines: List[str]
) -> ValidatorResult:
    """Return a copy of *source_result* carrying only *all_output_lines*."""
    output_line_separator = "\n"
    return ValidatorResult(
        name=source_result.name,
        checks=source_result.checks,
        passed=False,
        output=output_line_separator.join(all_output_lines),
    )


def _consume_exact_matches(
    all_line_identities: List[ViolationIdentity],
    remaining_exact: Counter[ViolationIdentity],
    remaining_by_key: Counter[tuple[str, str]],
) -> set[int]:
    """Mark the lines whose full identity matches an unconsumed baseline entry.

    Args:
        all_line_identities: One identity per located line, in output order.
        remaining_exact: The unconsumed baseline identity budget, decremented
            in place per match.
        remaining_by_key: The unconsumed per-key budget, decremented in step.

    Returns:
        The indexes of the exactly-matched lines.
    """
    all_matched_line_indexes: set[int] = set()
    for each_line_index, each_identity in enumerate(all_line_identities):
        if remaining_exact[each_identity] <= 0:
            continue
        remaining_exact[each_identity] -= 1
        remaining_by_key[each_identity[:IDENTITY_KEY_LENGTH]] -= 1
        all_matched_line_indexes.add(each_line_index)
    return all_matched_line_indexes


def _line_is_preexisting(
    line_index: int,
    all_line_identities: List[ViolationIdentity],
    all_matched_line_indexes: set[int],
    remaining_by_key: Counter[tuple[str, str]],
) -> bool:
    """Return whether one located line matches the baseline budget.

    An exact identity match is pre-existing. A leftover line whose
    ``(validator, enclosing function)`` key still has baseline budget is
    pre-existing with a drifted message. A line beyond its key's budget is new.

    Args:
        line_index: The line's position in the located-line order.
        all_line_identities: One identity per located line.
        all_matched_line_indexes: The exactly-matched line indexes.
        remaining_by_key: The unconsumed per-key budget, decremented in place.

    Returns:
        True when the line is pre-existing, False when it is new.
    """
    if line_index in all_matched_line_indexes:
        return True
    each_key = all_line_identities[line_index][:IDENTITY_KEY_LENGTH]
    if remaining_by_key[each_key] > 0:
        remaining_by_key[each_key] -= 1
        return True
    return False


def _partition_output_lines(
    each_result: ValidatorResult,
    name_by_line: dict[int, str],
    remaining_exact: Counter[ViolationIdentity],
    remaining_by_key: Counter[tuple[str, str]],
) -> tuple[List[str], List[str]]:
    """Split one result's located lines into a (new, pre-existing) line pair.

    The exact and per-key baseline budgets are consumed in place, exact
    matches first, so a later result never double-spends an earlier match.
    """
    located_lines = _located_violation_lines(each_result)
    all_line_identities = [
        _line_identity(each_result.name, each_line, name_by_line)
        for each_line in located_lines
    ]
    all_matched_line_indexes = _consume_exact_matches(
        all_line_identities, remaining_exact, remaining_by_key
    )
    all_new_lines: List[str] = []
    all_preexisting_lines: List[str] = []
    for each_line_index, each_line in enumerate(located_lines):
        is_preexisting = _line_is_preexisting(
            each_line_index, all_line_identities, all_matched_line_indexes, remaining_by_key
        )
        (all_preexisting_lines if is_preexisting else all_new_lines).append(each_line)
    return all_new_lines, all_preexisting_lines


def _grouped_result_lines(
    each_result: ValidatorResult, all_partitioned_lines: tuple[List[str], List[str]]
) -> tuple[List[ValidatorResult], List[ValidatorResult]]:
    """Return one result's (new, pre-existing) groups from its partitioned lines.

    A failed result with no located line at all cannot be baseline-matched, so
    it stays new in full — the gate fails closed rather than letting an
    unlocatable failure through.
    """
    all_new_lines, all_preexisting_lines = all_partitioned_lines
    if not all_new_lines and not all_preexisting_lines:
        return [each_result], []
    new_results = [_result_with_output(each_result, all_new_lines)] if all_new_lines else []
    preexisting_results = (
        [_result_with_output(each_result, all_preexisting_lines)]
        if all_preexisting_lines
        else []
    )
    return new_results, preexisting_results


def _scope_new_and_preexisting(
    all_proposed_failed_results: List[ValidatorResult],
    proposed_content: str,
    baseline_identities: Counter[ViolationIdentity],
) -> tuple[List[ValidatorResult], List[ValidatorResult]]:
    """Group proposed violations into newly-introduced and pre-existing results.

    Args:
        all_proposed_failed_results: The validators that fired on the proposed file.
        proposed_content: The reconstructed post-edit source text.
        baseline_identities: The identity counts the on-disk baseline carries.

    Returns:
        A ``(new_results, preexisting_results)`` pair.
    """
    name_by_line = _enclosing_function_name_by_line(proposed_content)
    remaining_exact = Counter(baseline_identities)
    remaining_by_key = _identity_key_counts(baseline_identities)
    all_new_results: List[ValidatorResult] = []
    all_preexisting_results: List[ValidatorResult] = []
    for each_result in all_proposed_failed_results:
        new_results, preexisting_results = _grouped_result_lines(
            each_result,
            _partition_output_lines(each_result, name_by_line, remaining_exact, remaining_by_key),
        )
        all_new_results.extend(new_results)
        all_preexisting_results.extend(preexisting_results)
    return all_new_results, all_preexisting_results
