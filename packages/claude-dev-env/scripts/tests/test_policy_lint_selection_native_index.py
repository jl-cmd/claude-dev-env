"""Preserve Git's active index without accepting repository-directory overrides."""

from __future__ import annotations

from pathlib import Path

import pytest
from policy_lint import selection_git


def test_active_git_index_survives_environment_sanitization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_path = tmp_path / "index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(index_path))
    monkeypatch.setenv("GIT_DIR", "foreign-repository")
    monkeypatch.setenv("GIT_WORK_TREE", "foreign-worktree")
    monkeypatch.setenv("PRESERVED_SETTING", "fixture")
    active_environment = selection_git._git_subprocess_environment()
    assert active_environment["GIT_INDEX_FILE"] == str(index_path)
    assert "GIT_DIR" not in active_environment
    assert "GIT_WORK_TREE" not in active_environment
    assert active_environment["PRESERVED_SETTING"] == "fixture"


def test_default_index_is_not_replaced_by_an_invented_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GIT_INDEX_FILE", raising=False)
    assert "GIT_INDEX_FILE" not in selection_git._git_subprocess_environment()
