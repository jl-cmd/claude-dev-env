import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _claude_permissions_common import (
    build_permission_rule,
    get_current_project_path,
    path_contains_glob_metacharacters,
)


def test_return_normalized_path_when_cwd_contains_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_with_spaces = tmp_path / "dir with spaces"
    directory_with_spaces.mkdir()
    monkeypatch.chdir(directory_with_spaces)
    returned_project_path = get_current_project_path()
    expected_suffix = "/dir with spaces"
    assert returned_project_path.endswith(expected_suffix)
    assert "\\" not in returned_project_path
    built_rule = build_permission_rule("Edit", returned_project_path)
    assert built_rule.startswith("Edit(")
    assert built_rule.endswith("/.claude/**)")
    assert "dir with spaces" in built_rule


def test_raise_when_cwd_contains_glob_metacharacters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_with_star = tmp_path / "weird[dir]"
    directory_with_star.mkdir()
    monkeypatch.chdir(directory_with_star)
    with pytest.raises(ValueError, match="glob metacharacters"):
        get_current_project_path()


def test_flag_glob_metacharacters_in_any_position() -> None:
    assert path_contains_glob_metacharacters("/home/user/[dir]/project")
    assert path_contains_glob_metacharacters("/home/user/project*")
    assert not path_contains_glob_metacharacters("/home/user/dir with spaces")
