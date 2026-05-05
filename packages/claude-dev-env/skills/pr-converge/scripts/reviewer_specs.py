"""Reviewer specifications shared by the per-reviewer fetch entry-point scripts.

A ReviewerSpec carries the two knobs that vary across the bugbot, copilot, and
claude reviewers: the case-insensitive substring used to match the reviewer's
GitHub login, and the callable that classifies a single review payload as
``"clean"`` or ``"dirty"``. The spec instances declared at module scope are
imported by the thin entry-point wrappers (``fetch_bugbot_reviews.py`` etc.)
and by ``reviewer_fetch_core``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    ALL_CLAUDE_DIRTY_REVIEW_STATES,
    ALL_COPILOT_DIRTY_REVIEW_STATES,
    BUGBOT_DIRTY_BODY_REGEX,
    CLAUDE_CLEAN_REVIEW_STATE,
    CLAUDE_LOGIN_FILTER_SUBSTRING,
    CLAUDE_SOFT_DIRTY_REVIEW_STATE,
    COPILOT_CLEAN_REVIEW_STATE,
    COPILOT_LOGIN_FILTER_SUBSTRING,
    COPILOT_SOFT_DIRTY_REVIEW_STATE,
    CURSOR_LOGIN_FILTER_SUBSTRING,
)
from review_field_helpers import body_of, state_of


@dataclass(frozen=True)
class ReviewerSpec:
    """Per-reviewer configuration: login substring filter plus classify callable."""

    login_filter_substring: str
    classify_review: Callable[[dict[str, object]], str]


def _classify_bugbot_review(field_by_key: dict[str, object]) -> str:
    review_body = body_of(field_by_key)
    if re.search(BUGBOT_DIRTY_BODY_REGEX, review_body):
        return "dirty"
    return "clean"


def _make_state_based_classifier(
    *,
    clean_state: str,
    all_dirty_states: tuple[str, ...],
    soft_dirty_state: str,
) -> Callable[[dict[str, object]], str]:
    def classify_review(field_by_key: dict[str, object]) -> str:
        review_state = state_of(field_by_key)
        if review_state == clean_state:
            return "clean"
        if review_state not in all_dirty_states:
            return "clean"
        if review_state == soft_dirty_state and not body_of(field_by_key):
            return "clean"
        return "dirty"

    return classify_review


bugbot_spec = ReviewerSpec(
    login_filter_substring=CURSOR_LOGIN_FILTER_SUBSTRING,
    classify_review=_classify_bugbot_review,
)


copilot_spec = ReviewerSpec(
    login_filter_substring=COPILOT_LOGIN_FILTER_SUBSTRING,
    classify_review=_make_state_based_classifier(
        clean_state=COPILOT_CLEAN_REVIEW_STATE,
        all_dirty_states=ALL_COPILOT_DIRTY_REVIEW_STATES,
        soft_dirty_state=COPILOT_SOFT_DIRTY_REVIEW_STATE,
    ),
)


claude_spec = ReviewerSpec(
    login_filter_substring=CLAUDE_LOGIN_FILTER_SUBSTRING,
    classify_review=_make_state_based_classifier(
        clean_state=CLAUDE_CLEAN_REVIEW_STATE,
        all_dirty_states=ALL_CLAUDE_DIRTY_REVIEW_STATES,
        soft_dirty_state=CLAUDE_SOFT_DIRTY_REVIEW_STATE,
    ),
)
