"""Tests for review_field_helpers.

Covers defensive field-coercion for the four GitHub payload field accessors
shared across fetch_*_reviews.py and fetch_*_inline_comments.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "review_field_helpers.py"
    spec = importlib.util.spec_from_file_location("review_field_helpers", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review_field_helpers_module = _load_module()


def test_login_of_should_return_login_string_when_user_dict_has_login() -> None:
    payload = {"user": {"login": "cursor[bot]"}}
    assert review_field_helpers_module.login_of(payload) == "cursor[bot]"


def test_login_of_should_return_none_when_user_field_missing() -> None:
    assert review_field_helpers_module.login_of({}) is None


def test_login_of_should_return_none_when_user_field_not_dict() -> None:
    assert review_field_helpers_module.login_of({"user": "not-a-dict"}) is None


def test_login_of_should_return_none_when_login_field_not_string() -> None:
    assert review_field_helpers_module.login_of({"user": {"login": 12345}}) is None


def test_body_of_should_return_body_string_when_present() -> None:
    assert review_field_helpers_module.body_of({"body": "review body"}) == "review body"


def test_body_of_should_return_empty_string_when_body_missing() -> None:
    assert review_field_helpers_module.body_of({}) == ""


def test_body_of_should_return_empty_string_when_body_not_string() -> None:
    assert review_field_helpers_module.body_of({"body": None}) == ""


def test_submitted_at_of_should_return_string_when_present() -> None:
    payload = {"submitted_at": "2026-05-03T12:00:00Z"}
    assert (
        review_field_helpers_module.submitted_at_of(payload) == "2026-05-03T12:00:00Z"
    )


def test_submitted_at_of_should_return_empty_string_when_missing() -> None:
    assert review_field_helpers_module.submitted_at_of({}) == ""


def test_submitted_at_of_should_return_empty_string_when_not_string() -> None:
    assert review_field_helpers_module.submitted_at_of({"submitted_at": 0}) == ""


def test_state_of_should_return_state_string_when_present() -> None:
    assert review_field_helpers_module.state_of({"state": "APPROVED"}) == "APPROVED"


def test_state_of_should_return_empty_string_when_missing() -> None:
    assert review_field_helpers_module.state_of({}) == ""


def test_state_of_should_return_empty_string_when_not_string() -> None:
    assert review_field_helpers_module.state_of({"state": ["APPROVED"]}) == ""
