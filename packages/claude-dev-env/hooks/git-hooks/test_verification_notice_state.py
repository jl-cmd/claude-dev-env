"""Tests for the base-reference construction in ``_base_matches_current``."""

from __future__ import annotations

from pathlib import Path

import pytest

import verification_notice
import verification_notice_state
from git_hooks_constants import COMMIT_OBJECT_NAME_SUFFIX
from git_hooks_constants.verification_notice_constants import (
    ALL_GIT_BASE_QUERY_PREFIX,
    BASE_REFERENCE,
)


def test_base_matches_current_queries_base_reference_plus_commit_suffix() -> None:
    captured_queries: list[tuple[str, ...]] = []

    def _fake_git_query(
        repository_root: Path, arguments: tuple[str, ...], capture_stderr: bool
    ) -> str | None:
        captured_queries.append(arguments)
        return "deadbeef"

    verification_notice_state._base_matches_current(Path("/repo"), "deadbeef", _fake_git_query)

    assert captured_queries == [
        (*ALL_GIT_BASE_QUERY_PREFIX, BASE_REFERENCE + COMMIT_OBJECT_NAME_SUFFIX)
    ]


def test_base_matches_current_derives_its_query_from_the_base_reference_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(verification_notice_state, "BASE_REFERENCE", "custom/base")
    captured_queries: list[tuple[str, ...]] = []

    def _fake_git_query(
        repository_root: Path, arguments: tuple[str, ...], capture_stderr: bool
    ) -> str | None:
        captured_queries.append(arguments)
        return None

    verification_notice_state._base_matches_current(Path("/repo"), "deadbeef", _fake_git_query)

    assert captured_queries == [
        (*ALL_GIT_BASE_QUERY_PREFIX, "custom/base" + COMMIT_OBJECT_NAME_SUFFIX)
    ]
