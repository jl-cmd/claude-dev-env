"""Tests for review_posting_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent / "config" / "review_posting_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "config.review_posting_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_reviews_path_template_renders_with_pull_number_placeholder() -> None:
    rendered_path = constants_module.REVIEWS_PATH_TEMPLATE.format(
        owner="o", repo="r", pull_number=42
    )
    assert rendered_path == "/repos/o/r/pulls/42/reviews?per_page=100"


def test_review_api_timeout_seconds_is_positive_integer() -> None:
    assert isinstance(constants_module.REVIEW_API_TIMEOUT_SECONDS, int)
    assert constants_module.REVIEW_API_TIMEOUT_SECONDS > 0


def test_review_comments_endpoint_template_renders_with_review_id() -> None:
    rendered_path = constants_module.REVIEW_COMMENTS_ENDPOINT_TEMPLATE.format(
        owner="o", repo="r", pull_number=42, review_id=99
    )
    assert rendered_path == "/repos/o/r/pulls/42/reviews/99/comments?per_page=100"


def test_status_ok_constant_pins_orchestrator_contract_string() -> None:
    """Producer/consumer contract: verify_review.py emits this exact string;
    the orchestrator reads it. Pinning here prevents silent drift between
    the two sides of the boundary.
    """
    assert constants_module.STATUS_OK == "ok"
    assert isinstance(constants_module.STATUS_OK, str)


def test_comments_fetch_status_ok_constant_pins_value() -> None:
    """Producer/consumer contract: post_audit_review.py emits this exact
    string when the follow-up GET succeeds; the orchestrator reads it to
    decide per-finding fix routing.
    """
    assert constants_module.COMMENTS_FETCH_STATUS_OK == "ok"
    assert isinstance(constants_module.COMMENTS_FETCH_STATUS_OK, str)


def test_comments_fetch_status_failed_constant_pins_value() -> None:
    """Producer/consumer contract: post_audit_review.py emits this exact
    string when the follow-up GET fails; the orchestrator reads it to fall
    back to parent-review-level replies.
    """
    assert constants_module.COMMENTS_FETCH_STATUS_FAILED == "failed"
    assert isinstance(constants_module.COMMENTS_FETCH_STATUS_FAILED, str)


def test_all_eventual_consistency_retry_delays_is_three_step_backoff() -> None:
    """The retry sequence absorbs GitHub's eventual-consistency window where
    a follow-up GET issued sub-second after POST may return an empty page.
    """
    assert constants_module.ALL_EVENTUAL_CONSISTENCY_RETRY_DELAYS == (0.5, 1.0, 2.0)
    assert isinstance(constants_module.ALL_EVENTUAL_CONSISTENCY_RETRY_DELAYS, tuple)
    assert all(
        isinstance(each_delay, float)
        for each_delay in constants_module.ALL_EVENTUAL_CONSISTENCY_RETRY_DELAYS
    )


def test_missing_string_field_constant_replaces_inline_empty_default() -> None:
    """Named replacement for the magic `""` default in
    `dict.get(key, "")` calls inside production function bodies.
    """
    assert constants_module.MISSING_STRING_FIELD == ""
    assert isinstance(constants_module.MISSING_STRING_FIELD, str)
