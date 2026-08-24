"""Classify Codex run streams into down-detail and gate outcome classes.

::

    classification = classify_codex_run(exit_code=1, stream_text=stderr_text)
    classification.detail_class   # usage_limit | auth_failure | ...
    classification.outcome_class  # codex_down | completed
"""

from __future__ import annotations

from dataclasses import dataclass

from codex_review_scripts_constants.classifier_constants import (
    ALL_AUTH_FAILURE_MARKERS,
    ALL_CONFIG_ERROR_MARKERS,
    ALL_MODEL_ERROR_MARKERS,
    ALL_USAGE_LIMIT_MARKERS,
    FAILURE_CLASS_AUTH_FAILURE,
    FAILURE_CLASS_CONFIG_ERROR,
    FAILURE_CLASS_MODEL_ERROR,
    FAILURE_CLASS_UNKNOWN,
    FAILURE_CLASS_USAGE_LIMIT,
    SUCCESS_EXIT_CODE,
)
from codex_review_scripts_constants.run_constants import (
    OUTCOME_CLASS_CODEX_DOWN,
    OUTCOME_CLASS_COMPLETED,
)


@dataclass(frozen=True)
class CodexRunClassification:
    """Fine-grained failure class plus the gate-level outcome class.

    ::

        CodexRunClassification(
            detail_class="config_error",
            outcome_class="codex_down",
        )

    Attributes:
        detail_class: ``completed`` or a failure class name.
        outcome_class: ``completed`` or ``codex_down`` for the conditional gate.
    """

    detail_class: str
    outcome_class: str


def _stream_contains_marker(stream_text: str, all_markers: tuple[str, ...]) -> bool:
    lowered_stream = stream_text.lower()
    return any(each_marker in lowered_stream for each_marker in all_markers)


def _classify_failure_detail(stream_text: str) -> str:
    if _stream_contains_marker(stream_text, ALL_CONFIG_ERROR_MARKERS):
        return FAILURE_CLASS_CONFIG_ERROR
    if _stream_contains_marker(stream_text, ALL_MODEL_ERROR_MARKERS):
        return FAILURE_CLASS_MODEL_ERROR
    if _stream_contains_marker(stream_text, ALL_USAGE_LIMIT_MARKERS):
        return FAILURE_CLASS_USAGE_LIMIT
    if _stream_contains_marker(stream_text, ALL_AUTH_FAILURE_MARKERS):
        return FAILURE_CLASS_AUTH_FAILURE
    return FAILURE_CLASS_UNKNOWN


def classify_codex_run(*, exit_code: int, stream_text: str) -> CodexRunClassification:
    """Map exit code and stream text to detail and gate outcome classes.

    ::

        classify_codex_run(exit_code=0, stream_text=success_jsonl)
        # ok: detail_class=completed, outcome_class=completed
        classify_codex_run(exit_code=1, stream_text="rate limit")
        # ok: detail_class=usage_limit, outcome_class=codex_down

    Exit zero is a completed review. Every other class — including
    ``unknown`` for nonzero exits and unparseable text — maps to
    ``codex_down`` so the conditional gate fails closed.

    Args:
        exit_code: Process exit code from the Codex review invocation.
        stream_text: Captured stdout JSONL and/or stderr text.

    Returns:
        Detail class and gate outcome class for the run.
    """
    if exit_code == SUCCESS_EXIT_CODE:
        return CodexRunClassification(
            detail_class=OUTCOME_CLASS_COMPLETED,
            outcome_class=OUTCOME_CLASS_COMPLETED,
        )
    return CodexRunClassification(
        detail_class=_classify_failure_detail(stream_text),
        outcome_class=OUTCOME_CLASS_CODEX_DOWN,
    )
