"""Behavioral tests for the Codex down-classifier."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import codex_down_classifier as classifier  # noqa: E402
from codex_review_scripts_constants.classifier_constants import (  # noqa: E402
    FAILURE_CLASS_AUTH_FAILURE,
    FAILURE_CLASS_CONFIG_ERROR,
    FAILURE_CLASS_MODEL_ERROR,
    FAILURE_CLASS_UNKNOWN,
    FAILURE_CLASS_USAGE_LIMIT,
)
from codex_review_scripts_constants.run_constants import (  # noqa: E402
    OUTCOME_CLASS_CODEX_DOWN,
    OUTCOME_CLASS_COMPLETED,
)

FIXTURES_DIRECTORY = SCRIPTS_DIRECTORY / "fixtures"


def _read_fixture(fixture_name: str) -> str:
    return (FIXTURES_DIRECTORY / fixture_name).read_text(encoding="utf-8")


def test_config_load_failure_fixture_maps_to_config_error() -> None:
    stream_text = _read_fixture("config_load_failure_v0.125.0.txt")

    classification = classifier.classify_codex_run(
        exit_code=1,
        stream_text=stream_text,
    )

    assert classification.detail_class == FAILURE_CLASS_CONFIG_ERROR
    assert classification.outcome_class == OUTCOME_CLASS_CODEX_DOWN


def test_model_rejection_fixture_maps_to_model_error() -> None:
    stream_text = _read_fixture("model_rejection_v0.125.0.jsonl")

    classification = classifier.classify_codex_run(
        exit_code=1,
        stream_text=stream_text,
    )

    assert classification.detail_class == FAILURE_CLASS_MODEL_ERROR
    assert classification.outcome_class == OUTCOME_CLASS_CODEX_DOWN


def test_success_stream_fixture_maps_to_completed() -> None:
    stream_text = _read_fixture("success_stream_v0.144.3.jsonl")

    classification = classifier.classify_codex_run(
        exit_code=0,
        stream_text=stream_text,
    )

    assert classification.detail_class == OUTCOME_CLASS_COMPLETED
    assert classification.outcome_class == OUTCOME_CLASS_COMPLETED


def test_usage_limit_maps_to_codex_down() -> None:
    stream_text = _read_fixture("usage_limit_synthetic.txt")

    classification = classifier.classify_codex_run(
        exit_code=1,
        stream_text=stream_text,
    )

    assert classification.detail_class == FAILURE_CLASS_USAGE_LIMIT
    assert classification.outcome_class == OUTCOME_CLASS_CODEX_DOWN


def test_auth_failure_maps_to_codex_down() -> None:
    stream_text = _read_fixture("auth_failure_synthetic.txt")

    classification = classifier.classify_codex_run(
        exit_code=1,
        stream_text=stream_text,
    )

    assert classification.detail_class == FAILURE_CLASS_AUTH_FAILURE
    assert classification.outcome_class == OUTCOME_CLASS_CODEX_DOWN


def test_unknown_nonzero_exit_maps_to_codex_down() -> None:
    stream_text = _read_fixture("unknown_failure_synthetic.txt")

    classification = classifier.classify_codex_run(
        exit_code=1,
        stream_text=stream_text,
    )

    assert classification.detail_class == FAILURE_CLASS_UNKNOWN
    assert classification.outcome_class == OUTCOME_CLASS_CODEX_DOWN


def test_unparseable_nonzero_exit_maps_to_codex_down() -> None:
    classification = classifier.classify_codex_run(
        exit_code=2,
        stream_text="",
    )

    assert classification.detail_class == FAILURE_CLASS_UNKNOWN
    assert classification.outcome_class == OUTCOME_CLASS_CODEX_DOWN
