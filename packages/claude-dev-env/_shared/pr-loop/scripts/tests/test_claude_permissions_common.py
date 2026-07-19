"""Tests for _shared permission helpers extracted from skills/bugteam/scripts/."""

import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_common_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "_claude_permissions_common.py"
    parent_directory = str(module_path.parent.resolve())
    if parent_directory in sys.path:
        sys.path.remove(parent_directory)
    sys.path.insert(0, parent_directory)
    for each_module_name in list(sys.modules):
        if each_module_name == "pr_loop_shared_constants" or each_module_name.startswith(
            "pr_loop_shared_constants."
        ):
            del sys.modules[each_module_name]
        if each_module_name == "_claude_permissions_common":
            del sys.modules[each_module_name]
    spec = importlib.util.spec_from_file_location(
        "_claude_permissions_common", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_claude_permissions_common"] = module
    spec.loader.exec_module(module)
    return module


common = _load_common_module()


def test_return_normalized_path_when_cwd_contains_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_with_spaces = tmp_path / "dir with spaces"
    directory_with_spaces.mkdir()
    monkeypatch.chdir(directory_with_spaces)
    returned_project_path = common.get_current_project_path()
    expected_suffix = "/dir with spaces"
    assert returned_project_path.endswith(expected_suffix)
    assert "\\" not in returned_project_path
    built_rule = common.build_permission_rule("Edit", returned_project_path)
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
        common.get_current_project_path()


def test_flag_glob_metacharacters_in_any_position() -> None:
    assert common.path_contains_glob_metacharacters("/home/user/[dir]/project")
    assert common.path_contains_glob_metacharacters("/home/user/project*")
    assert not common.path_contains_glob_metacharacters("/home/user/dir with spaces")


def test_text_file_encoding_remains_local_constant() -> None:
    assert common.TEXT_FILE_ENCODING == "utf-8"


def test_module_no_longer_redeclares_migrated_constants() -> None:
    assert not hasattr(common, "ALL_PERMISSION_ALLOW_TOOLS")
    assert not hasattr(common, "AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE")


def test_save_settings_uses_unique_per_call_temp_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for atomic-write race: each save_settings call must
    derive its own unique temp path so concurrent writers do not collide
    on the same `.tmp` filename.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({}), encoding="utf-8")

    captured_temp_paths: list[Path] = []
    real_write_atomically_with_mode = common.write_atomically_with_mode

    def capturing_write(
        temporary_path: Path, serialized_content: str, file_mode: int
    ) -> None:
        captured_temp_paths.append(Path(temporary_path))
        real_write_atomically_with_mode(
            temporary_path, serialized_content, file_mode
        )

    monkeypatch.setattr(common, "write_atomically_with_mode", capturing_write)

    common.save_settings(settings_path, {"writer": "first"})
    common.save_settings(settings_path, {"writer": "second"})

    assert len(captured_temp_paths) == 2
    assert captured_temp_paths[0] != captured_temp_paths[1]
    for each_temp_path in captured_temp_paths:
        assert ".tmp." in each_temp_path.name


def test_save_settings_temp_suffix_includes_pid_and_random_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unique temp suffix must include the process id and a random
    hex token so two processes cannot collide on the same temp filename.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({}), encoding="utf-8")

    captured_temp_paths: list[Path] = []
    real_write_atomically_with_mode = common.write_atomically_with_mode

    def capturing_write(
        temporary_path: Path, serialized_content: str, file_mode: int
    ) -> None:
        captured_temp_paths.append(Path(temporary_path))
        real_write_atomically_with_mode(
            temporary_path, serialized_content, file_mode
        )

    monkeypatch.setattr(common, "write_atomically_with_mode", capturing_write)

    common.save_settings(settings_path, {"writer": "only"})

    assert len(captured_temp_paths) == 1
    suffix_token = captured_temp_paths[0].name.split(".tmp.", maxsplit=1)[1]
    pid_text, random_token = suffix_token.split(".", maxsplit=1)
    assert pid_text.isdigit()
    minimum_random_token_hex_chars = 4
    assert len(random_token) >= minimum_random_token_hex_chars
    assert all(
        each_character in "0123456789abcdef" for each_character in random_token
    )


def test_text_file_encoding_sourced_from_config() -> None:
    config_module_path = (
        Path(__file__).parent.parent
        / "pr_loop_shared_constants"
        / "claude_permissions_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "pr_loop_shared_constants.claude_permissions_constants", config_module_path
    )
    assert specification is not None
    assert specification.loader is not None
    config_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(config_module)
    assert common.TEXT_FILE_ENCODING == config_module.TEXT_FILE_ENCODING


def test_path_contains_glob_metacharacters_local_tuple_uses_all_collection_prefix() -> None:
    source_text = inspect.getsource(common.path_contains_glob_metacharacters)
    assert "all_glob_metacharacters_in_path" in source_text
    assert "glob_metacharacters_in_path:" not in source_text.replace(
        "all_glob_metacharacters_in_path", ""
    )


def test_is_valid_project_root_detects_git_marker(tmp_path: Path) -> None:
    git_project_root = tmp_path / "git_project"
    (git_project_root / ".git").mkdir(parents=True)
    assert common.is_valid_project_root(git_project_root) is True


def test_is_valid_project_root_detects_claude_marker(tmp_path: Path) -> None:
    claude_project_root = tmp_path / "claude_project"
    (claude_project_root / ".claude").mkdir(parents=True)
    assert common.is_valid_project_root(claude_project_root) is True


def test_is_valid_project_root_rejects_unmarked_directory(tmp_path: Path) -> None:
    unmarked_directory = tmp_path / "no_marker"
    unmarked_directory.mkdir()
    assert common.is_valid_project_root(unmarked_directory) is False


def test_is_valid_project_root_uses_extracted_directory_marker_constants() -> None:
    """is_valid_project_root must reference extracted constants, not inline string literals."""
    source_text = inspect.getsource(common.is_valid_project_root)
    assert "GIT_DIRECTORY_NAME" in source_text
    assert "CLAUDE_SETTINGS_DIRECTORY_NAME" in source_text
    assert "'.git'" not in source_text
    assert '".git"' not in source_text
    assert "'.claude'" not in source_text
    assert '".claude"' not in source_text

def test_permission_rule_tool_name_extracts_tool_prefix() -> None:
    assert common.permission_rule_tool_name("Edit(/repo/.claude/**)") == "Edit"
    assert common.permission_rule_tool_name("Write(c:/Users/jon/.claude/worktrees/x/**)") == (
        "Write"
    )
    assert common.permission_rule_tool_name(None) is None
    assert common.permission_rule_tool_name("not-a-rule") is None


def test_is_inert_file_permission_rule_for_write_glob_notebookedit() -> None:
    assert common.is_inert_file_permission_rule("Write(/wt/.claude/**)") is True
    assert common.is_inert_file_permission_rule("Glob(/wt/.claude/hooks/**)") is True
    assert common.is_inert_file_permission_rule("NotebookEdit(**/.claude/worktrees/**)") is True
    assert common.is_inert_file_permission_rule("Edit(/repo/.claude/**)") is False
    assert common.is_inert_file_permission_rule("Bash(echo hi)") is False


def test_all_project_path_aliases_for_reap_adds_home_alias_when_project_is_home() -> None:
    all_aliases = common.all_project_path_aliases_for_reap(
        "C:/Users/jon", home_directory_path="C:/Users/jon"
    )
    assert all_aliases == ("C:/Users/jon", "$HOME")


def test_all_project_path_aliases_for_reap_skips_home_alias_for_other_projects() -> None:
    all_aliases = common.all_project_path_aliases_for_reap(
        "C:/dev/other", home_directory_path="C:/Users/jon"
    )
    assert all_aliases == ("C:/dev/other",)
