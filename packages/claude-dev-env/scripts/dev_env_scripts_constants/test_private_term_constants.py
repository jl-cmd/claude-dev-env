"""Tests for the private-term digest table."""

from __future__ import annotations

import re

from dev_env_scripts_constants.private_term_constants import (
    ALL_EVENT_TEXT_FIELDS,
    ALL_PRIVATE_TERM_DIGESTS,
)

_SHA256_HEX_PATTERN = re.compile(r"[0-9a-f]{64}")


def test_should_ship_only_digests_of_named_lengths() -> None:
    assert ALL_PRIVATE_TERM_DIGESTS
    for each_digest in ALL_PRIVATE_TERM_DIGESTS:
        assert _SHA256_HEX_PATTERN.fullmatch(each_digest.sha256)
        assert each_digest.length > 0


def test_should_read_every_text_a_pull_request_issue_comment_review_or_release_carries() -> None:
    assert {each_object for each_object, _field, _label in ALL_EVENT_TEXT_FIELDS} == {
        "pull_request",
        "issue",
        "comment",
        "review",
        "release",
    }
