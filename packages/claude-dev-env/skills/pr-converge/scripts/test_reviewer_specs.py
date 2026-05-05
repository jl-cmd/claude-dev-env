"""Tests for reviewer_specs.

Covers:
- each ReviewerSpec instance carries the documented login_filter_substring
- bugbot_spec.classify_review uses the dirty-body regex
- copilot_spec.classify_review dispatches off review state plus body
- claude_spec.classify_review dispatches off review state plus body
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "reviewer_specs.py"
    spec = importlib.util.spec_from_file_location("reviewer_specs", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reviewer_specs_module = _load_module()


def test_bugbot_spec_uses_cursor_login_filter_substring() -> None:
    assert reviewer_specs_module.bugbot_spec.login_filter_substring == "cursor"


def test_copilot_spec_uses_copilot_login_filter_substring() -> None:
    assert reviewer_specs_module.copilot_spec.login_filter_substring == "copilot"


def test_claude_spec_uses_claude_login_filter_substring() -> None:
    assert reviewer_specs_module.claude_spec.login_filter_substring == "claude"


def test_bugbot_classify_returns_dirty_when_body_matches_findings_pattern() -> None:
    review_payload = {
        "body": "Cursor Bugbot has reviewed your changes and found 2 potential issues.",
    }
    assert reviewer_specs_module.bugbot_spec.classify_review(review_payload) == "dirty"


def test_bugbot_classify_returns_clean_when_body_lacks_findings_pattern() -> None:
    review_payload = {
        "body": "Bugbot reviewed your changes and found no new issues!",
    }
    assert reviewer_specs_module.bugbot_spec.classify_review(review_payload) == "clean"


def test_copilot_classify_returns_clean_when_state_is_approved() -> None:
    review_payload = {"state": "APPROVED", "body": "lgtm"}
    assert reviewer_specs_module.copilot_spec.classify_review(review_payload) == "clean"


def test_copilot_classify_returns_dirty_when_state_is_changes_requested() -> None:
    review_payload = {"state": "CHANGES_REQUESTED", "body": "fix this"}
    assert reviewer_specs_module.copilot_spec.classify_review(review_payload) == "dirty"


def test_copilot_classify_returns_dirty_when_state_is_commented_with_body() -> None:
    review_payload = {"state": "COMMENTED", "body": "minor nit"}
    assert reviewer_specs_module.copilot_spec.classify_review(review_payload) == "dirty"


def test_copilot_classify_returns_clean_when_state_is_commented_with_empty_body() -> (
    None
):
    review_payload = {"state": "COMMENTED", "body": ""}
    assert reviewer_specs_module.copilot_spec.classify_review(review_payload) == "clean"


def test_copilot_classify_returns_clean_when_state_is_unknown() -> None:
    review_payload = {"state": "DISMISSED", "body": "ignored"}
    assert reviewer_specs_module.copilot_spec.classify_review(review_payload) == "clean"


def test_claude_classify_returns_clean_when_state_is_approved() -> None:
    review_payload = {"state": "APPROVED", "body": "lgtm"}
    assert reviewer_specs_module.claude_spec.classify_review(review_payload) == "clean"


def test_claude_classify_returns_dirty_when_state_is_changes_requested() -> None:
    review_payload = {"state": "CHANGES_REQUESTED", "body": "fix this"}
    assert reviewer_specs_module.claude_spec.classify_review(review_payload) == "dirty"


def test_claude_classify_returns_dirty_when_state_is_commented_with_body() -> None:
    review_payload = {"state": "COMMENTED", "body": "minor nit"}
    assert reviewer_specs_module.claude_spec.classify_review(review_payload) == "dirty"


def test_claude_classify_returns_clean_when_state_is_commented_with_empty_body() -> (
    None
):
    review_payload = {"state": "COMMENTED", "body": ""}
    assert reviewer_specs_module.claude_spec.classify_review(review_payload) == "clean"


def test_claude_classify_returns_clean_when_state_is_unknown() -> None:
    review_payload = {"state": "DISMISSED", "body": "ignored"}
    assert reviewer_specs_module.claude_spec.classify_review(review_payload) == "clean"
