"""Specifications that every tool reads the repository skills from one home.

Codex reads ``.agents/skills``. Claude Code reads ``.claude/skills`` and Cursor
reads ``.cursor/skills``, and both of those are directory pointers to
``.agents/skills``, so a skill or a feature map lives in one place.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_SYMLINK_MODE = "120000"
_SKILLS_HOME_TARGET = "../.agents/skills"
_ALL_POINTER_PATHS = (".claude/skills", ".cursor/skills")
_FEATURE_LINK_PATTERN = re.compile(r"\]\(\.?/?([^)#]+\.md)\)")


def _repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git_output(*all_arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(_repository_root()), *all_arguments],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    return completed.stdout


@pytest.mark.parametrize("pointer_path", _ALL_POINTER_PATHS)
def test_tool_skill_directory_should_be_a_pointer_to_the_agents_home(
    pointer_path: str,
) -> None:
    index_entry = _git_output("ls-files", "--stage", "--", pointer_path).split()
    assert index_entry, f"{pointer_path} is not tracked as a directory pointer"
    mode, blob_id = index_entry[0], index_entry[1]
    assert mode == _SYMLINK_MODE, (
        f"{pointer_path} is tracked as mode {mode}; a pointer is mode {_SYMLINK_MODE}"
    )
    assert _git_output("cat-file", "blob", blob_id) == _SKILLS_HOME_TARGET


def test_verify_feature_index_should_link_every_feature_map() -> None:
    features_directory = (
        _repository_root() / ".agents" / "skills" / "verify" / "features"
    )
    index_text = (features_directory / "README.md").read_text(encoding="utf-8")
    linked_names = set(_FEATURE_LINK_PATTERN.findall(index_text))
    map_names = {
        each_path.name
        for each_path in features_directory.glob("*.md")
        if each_path.name != "README.md"
    }
    assert map_names == linked_names
