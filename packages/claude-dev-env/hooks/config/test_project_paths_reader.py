"""Tests for project_paths_reader — config reader for ~/.claude/project-paths.json."""

import inspect
import json
import sys
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config import project_paths_reader
from config.project_paths_reader import (
    load_registry,
    registry_contains_path,
    registry_file_path,
)
from config.setup_project_paths_constants import META_KEY


def test_reader_does_not_redefine_dynamic_stderr_handler_locally() -> None:
    """Pin PR #230 round 3 DRY fix: handler is imported from the shared module.

    Both project_paths_reader and es_exe_path_rewriter previously defined
    identical `_DynamicStderrHandler` classes. This test fails if the
    duplicate class reappears in project_paths_reader.
    """
    assert not hasattr(project_paths_reader, "_DynamicStderrHandler")


def test_load_registry_returns_empty_dict_when_file_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "nonexistent.json"
    loaded_registry = load_registry(config_path=missing_path)
    assert loaded_registry == {}


def test_load_registry_returns_empty_dict_when_json_is_malformed(
    tmp_path: Path,
) -> None:
    malformed_file = tmp_path / "project-paths.json"
    malformed_file.write_text("{ not valid json", encoding="utf-8")
    loaded_registry = load_registry(config_path=malformed_file)
    assert loaded_registry == {}


def test_load_registry_strips_meta_key(tmp_path: Path) -> None:
    registry_file = tmp_path / "project-paths.json"
    registry_file.write_text(
        json.dumps(
            {
                "_meta": {"schema_version": 1, "last_scan": "2026-01-01T00:00:00Z"},
                "my-repo": "Y:\\Projects\\my-repo",
            }
        ),
        encoding="utf-8",
    )
    loaded_registry = load_registry(config_path=registry_file)
    assert "_meta" not in loaded_registry
    assert loaded_registry["my-repo"] == "Y:\\Projects\\my-repo"


def test_load_registry_returns_name_to_path_mapping(tmp_path: Path) -> None:
    registry_file = tmp_path / "project-paths.json"
    registry_file.write_text(
        json.dumps(
            {
                "repo-alpha": "Y:\\Projects\\repo-alpha",
                "repo-beta": "C:\\Dev\\repo-beta",
            }
        ),
        encoding="utf-8",
    )
    loaded_registry = load_registry(config_path=registry_file)
    assert loaded_registry == {
        "repo-alpha": "Y:\\Projects\\repo-alpha",
        "repo-beta": "C:\\Dev\\repo-beta",
    }


def test_load_registry_returns_empty_dict_when_top_level_is_not_object(
    tmp_path: Path,
) -> None:
    registry_file = tmp_path / "project-paths.json"
    registry_file.write_text(json.dumps(["a", "b"]), encoding="utf-8")
    loaded_registry = load_registry(config_path=registry_file)
    assert loaded_registry == {}


def test_registry_contains_path_returns_true_when_path_present(tmp_path: Path) -> None:
    known_registry = {"my-repo": str(tmp_path)}
    assert registry_contains_path(known_registry, str(tmp_path)) is True


def test_registry_contains_path_returns_false_when_path_absent(tmp_path: Path) -> None:
    known_registry = {"other-repo": "C:\\Other\\Path"}
    assert registry_contains_path(known_registry, str(tmp_path)) is False


def test_registry_contains_path_normalizes_separators(tmp_path: Path) -> None:
    forward_slash_path = str(tmp_path).replace("\\", "/")
    known_registry = {"my-repo": str(tmp_path)}
    assert registry_contains_path(known_registry, forward_slash_path) is True


def test_registry_contains_path_treats_backslash_and_forward_slash_as_equal() -> None:
    backslash_path = "C:\\foo\\bar"
    forward_slash_path = "C:/foo/bar"
    known_registry = {"my-repo": backslash_path}
    assert registry_contains_path(known_registry, forward_slash_path) is True
    known_registry_forward = {"my-repo": forward_slash_path}
    assert registry_contains_path(known_registry_forward, backslash_path) is True


def test_registry_file_path_returns_dot_claude_project_paths_json() -> None:
    resolved_path = registry_file_path()
    assert resolved_path.name == "project-paths.json"
    assert resolved_path.parent.name == ".claude"
    assert resolved_path.parent.parent == Path.home()


def test_registry_file_path_is_absolute() -> None:
    resolved_path = registry_file_path()
    assert resolved_path.is_absolute()


def test_load_registry_uses_shared_meta_key_constant() -> None:
    """Pin: load_registry must import META_KEY from setup_project_paths_constants.

    The bare string literal "_meta" must not appear in load_registry;
    it must use the shared META_KEY constant as the single source of truth.
    """
    source = inspect.getsource(project_paths_reader.load_registry)
    assert '"_meta"' not in source, (
        'load_registry must use META_KEY constant, not the bare literal "_meta"'
    )


def test_load_registry_uses_shared_utf8_encoding_constant() -> None:
    """Pin fix_1: load_registry must import UTF8_ENCODING from setup_project_paths_constants.

    The bare string literal "utf-8" in the read_text call must be replaced
    with the shared constant so there is one source of truth for the encoding name.
    """
    source = inspect.getsource(project_paths_reader)
    assert 'encoding="utf-8"' not in source, (
        'load_registry must use UTF8_ENCODING constant, not the bare literal "utf-8"'
    )
