"""Regression tests for the leading-underscore _claude_permissions_common module.

The companion test_claude_permissions_common.py covers the public-name
matched suite. This file holds tests the TDD enforcer pairs to the
leading-underscore production filename.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_common_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "_claude_permissions_common.py"
    parent_directory = str(module_path.parent.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    spec = importlib.util.spec_from_file_location(
        "_claude_permissions_common", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _load_common_module()


def test_save_settings_chmods_after_replace_to_defeat_umask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: POSIX umask masks the mode passed to os.open, so the
    "preserve mode" intent is silently defeated unless save_settings
    chmods the final file after os.replace.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({}), encoding="utf-8")
    captured_mode_to_preserve = 0o600
    monkeypatch.setattr(
        common, "get_mode_to_preserve", lambda _path: captured_mode_to_preserve
    )

    ordered_calls: list[tuple[str, str, int | None]] = []
    real_replace = common.os.replace
    real_chmod = common.os.chmod

    def recording_replace(source_path: str, destination_path: str) -> None:
        ordered_calls.append(("replace", str(destination_path), None))
        real_replace(source_path, destination_path)

    def recording_chmod(target_path: str, file_mode: int) -> None:
        ordered_calls.append(("chmod", str(target_path), file_mode))
        real_chmod(target_path, file_mode)

    monkeypatch.setattr(common.os, "replace", recording_replace)
    monkeypatch.setattr(common.os, "chmod", recording_chmod)

    common.save_settings(settings_path, {"writer": "only"})

    final_replace_index = next(
        each_index
        for each_index, each_call in enumerate(ordered_calls)
        if each_call[0] == "replace" and each_call[1] == str(settings_path)
    )
    final_chmod_index = next(
        (
            each_index
            for each_index, each_call in enumerate(ordered_calls)
            if each_call[0] == "chmod"
            and each_call[1] == str(settings_path)
            and each_call[2] == captured_mode_to_preserve
        ),
        None,
    )
    assert final_chmod_index is not None
    assert final_replace_index < final_chmod_index


def test_path_contains_glob_metacharacters_rejects_true_metacharacters() -> None:
    assert common.path_contains_glob_metacharacters("C:/some/path/*.py") is True
    assert common.path_contains_glob_metacharacters("C:/some/path/[abc].py") is True
    assert common.path_contains_glob_metacharacters("C:/some/{a,b}/file") is True




def test_write_atomically_with_mode_closes_descriptor_when_fdopen_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: if os.fdopen fails, the raw descriptor from os.open must close.

    Cursor Bugbot: without a failure path, the descriptor
    leaks when fdopen raises before the file object assumes ownership.
    """
    closed_descriptors: list[int] = []
    sentinel_descriptor = 91

    def fake_open(_path: str, _flags: int, _mode: int = 0o777) -> int:
        return sentinel_descriptor

    def fake_fdopen(_file_descriptor: int, *_args: object, **_kwargs: object) -> object:
        raise OSError("simulated fdopen failure")

    def recording_close(file_descriptor: int) -> None:
        closed_descriptors.append(file_descriptor)

    monkeypatch.setattr(common.os, "open", fake_open)
    monkeypatch.setattr(common.os, "fdopen", fake_fdopen)
    monkeypatch.setattr(common.os, "close", recording_close)

    temporary_path = tmp_path / "tempfile.tmp"
    with pytest.raises(OSError, match="simulated fdopen failure"):
        common.write_atomically_with_mode(temporary_path, "{}", 0o600)

    assert closed_descriptors == [sentinel_descriptor]


def test_path_contains_glob_metacharacters_accepts_windows_paths_with_parens() -> None:
    """Regression: Windows paths like C:/Program Files (x86)/ must not raise ValueError.

    `(`, `)`, and `,` are not glob metacharacters in Claude Code's permission
    rule matching. Including them in the metacharacter set causes
    get_current_project_path to raise ValueError for any user whose home
    directory contains parentheses (e.g. `C:/Users/Jon (Admin)/...`).
    """
    assert common.path_contains_glob_metacharacters("C:/Program Files (x86)/app") is False
    assert common.path_contains_glob_metacharacters("C:/Users/Jon (Admin)/project") is False
    assert common.path_contains_glob_metacharacters("C:/Projects/a,b/file.py") is False


def test_get_mode_to_preserve_returns_existing_file_mode(tmp_path: Path) -> None:
    """When the file exists, the actual filesystem mode must be returned (not the default)."""
    target_path = tmp_path / "settings.json"
    target_path.write_text("{}", encoding="utf-8")
    actual_filesystem_mode = target_path.stat().st_mode & 0o777
    returned_mode = common.get_mode_to_preserve(target_path)
    assert returned_mode == actual_filesystem_mode


def test_get_mode_to_preserve_returns_secure_default_when_file_missing(
    tmp_path: Path,
) -> None:
    """A missing settings file must fall back to the secure 0o600 default mode."""
    missing_settings_path = tmp_path / "no_such_file.json"
    returned_mode = common.get_mode_to_preserve(missing_settings_path)
    assert returned_mode == 0o600


def test_write_atomically_with_mode_raises_oserror_when_open_fails(
    tmp_path: Path,
) -> None:
    """OSError from os.open must propagate to the caller."""
    target_path = tmp_path / "subdirectory" / "missing" / "settings.json.tmp"
    with pytest.raises(OSError):
        common.write_atomically_with_mode(target_path, "payload", file_mode=0o600)


def test_write_atomically_with_mode_unlinks_temp_when_fdopen_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure inside os.fdopen must remove the on-disk temp file.

    The file exists the moment os.open returns; closing only the raw
    descriptor would leave an empty temp sibling on disk after the
    exception propagates to the caller.
    """

    def failing_fdopen(*_args: object, **_kwargs: object) -> object:
        raise MemoryError("fdopen failure")

    monkeypatch.setattr(common.os, "fdopen", failing_fdopen)
    target_path = tmp_path / "settings.json.tmp"
    with pytest.raises(MemoryError):
        common.write_atomically_with_mode(target_path, "payload", file_mode=0o600)
    assert not target_path.exists(), (
        "the temp file created by os.open must be unlinked before re-raising"
    )


def test_save_settings_warns_on_stderr_when_temp_unlink_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A swallowed unlink in the finally block must surface to stderr.

    Forces a write success followed by os.replace failure so the temp file
    survives into the finally branch, then makes Path.unlink raise.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"existing": true}\n', encoding="utf-8")

    def failing_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("replace blocked by AV")

    def failing_unlink(_self: Path, *_args: object, **_kwargs: object) -> None:
        raise PermissionError("temp file held by AV")

    monkeypatch.setattr(common.os, "replace", failing_replace)
    monkeypatch.setattr(Path, "unlink", failing_unlink)
    with pytest.raises(SystemExit):
        common.save_settings(settings_path, {"new_key": "value"})
    captured = capsys.readouterr()
    assert ".tmp" in captured.err
    assert "PermissionError" in captured.err or "held by AV" in captured.err


def test_save_settings_finally_skips_unlink_when_no_temp_was_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When this invocation never created the temp file, finally must not unlink it."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"existing": true}\n', encoding="utf-8")

    unlink_call_paths: list[Path] = []
    original_unlink = Path.unlink

    def recording_unlink(unlink_target: Path, *args: object, **kwargs: object) -> None:
        unlink_call_paths.append(unlink_target)
        original_unlink(unlink_target, *args, **kwargs)

    def write_raises(*_args: object, **_kwargs: object) -> None:
        raise FileExistsError("another writer's temp")

    monkeypatch.setattr(common, "write_atomically_with_mode", write_raises)
    monkeypatch.setattr(Path, "unlink", recording_unlink)
    with pytest.raises(SystemExit):
        common.save_settings(settings_path, {"new_key": "value"})
    assert not any(
        ".tmp." in each_path.name for each_path in unlink_call_paths
    ), "finally must not unlink a temp file this invocation never created"


def test_exit_with_error_prints_prefixed_message_and_exits_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised_exit:
        common.exit_with_error("boom")
    assert raised_exit.value.code == 1
    assert "Error: boom" in capsys.readouterr().err


def test_build_permission_rules_builds_one_rule_per_tool() -> None:
    built_rules = common.build_permission_rules("/proj", ("Edit", "Read"))
    assert built_rules == ["Edit(/proj/.claude/**)", "Read(/proj/.claude/**)"]


def test_build_agent_config_deny_rule_embeds_tool_path_and_pattern() -> None:
    built_rule = common.build_agent_config_deny_rule("Write", "/proj", "hooks/**")
    assert built_rule == "Write(/proj/.claude/hooks/**)"


def test_remove_matching_entries_from_list_filters_in_place_and_counts() -> None:
    all_entries: list[object] = ["keep", "drop", "drop", 7]
    removed_count = common.remove_matching_entries_from_list(
        all_entries, lambda each_entry: each_entry == "drop"
    )
    assert removed_count == 2
    assert all_entries == ["keep", 7]


def test_load_settings_returns_empty_dict_when_file_missing(tmp_path: Path) -> None:
    assert common.load_settings(tmp_path / "absent.json") == {}


def test_load_settings_parses_existing_json_object(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"permissions": {"allow": []}}', encoding="utf-8")
    assert common.load_settings(settings_path) == {"permissions": {"allow": []}}


def test_load_settings_exits_when_file_holds_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        common.load_settings(settings_path)
    assert "not valid JSON" in capsys.readouterr().err


def test_serialize_settings_to_json_text_sorts_keys() -> None:
    serialized_text = common.serialize_settings_to_json_text({"b": 1, "a": 2})
    assert serialized_text.index('"a"') < serialized_text.index('"b"')
    assert json.loads(serialized_text) == {"a": 2, "b": 1}


def test_append_if_missing_appends_only_new_values() -> None:
    all_entries: list[object] = ["existing"]
    assert common.append_if_missing(all_entries, "fresh") is True
    assert common.append_if_missing(all_entries, "fresh") is False
    assert all_entries == ["existing", "fresh"]


def test_ensure_dict_section_creates_missing_and_returns_existing() -> None:
    all_settings: dict[str, object] = {}
    created_section = common.ensure_dict_section(all_settings, "permissions")
    assert created_section == {}
    assert all_settings["permissions"] is created_section
    assert common.ensure_dict_section(all_settings, "permissions") is created_section


def test_ensure_dict_section_exits_on_non_dict_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    all_settings: dict[str, object] = {"permissions": "oops"}
    with pytest.raises(SystemExit):
        common.ensure_dict_section(all_settings, "permissions")
    assert "not a JSON object" in capsys.readouterr().err


def test_ensure_list_entry_creates_missing_and_returns_existing() -> None:
    permissions_section: dict[str, object] = {}
    created_entry = common.ensure_list_entry(permissions_section, "allow")
    assert created_entry == []
    assert permissions_section["allow"] is created_entry
    assert common.ensure_list_entry(permissions_section, "allow") is created_entry


def test_ensure_list_entry_exits_on_non_list_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    permissions_section: dict[str, object] = {"allow": {}}
    with pytest.raises(SystemExit):
        common.ensure_list_entry(permissions_section, "allow")
    assert "not a JSON array" in capsys.readouterr().err


def test_prune_empty_list_then_empty_section_removes_empty_structures() -> None:
    all_settings: dict[str, object] = {"permissions": {"allow": []}}
    common.prune_empty_list_then_empty_section(all_settings, "permissions", "allow")
    assert all_settings == {}


def test_prune_empty_list_then_empty_section_keeps_populated_structures() -> None:
    all_settings: dict[str, object] = {
        "permissions": {"allow": ["Edit(/proj/.claude/**)"], "deny": []}
    }
    common.prune_empty_list_then_empty_section(all_settings, "permissions", "deny")
    assert all_settings == {"permissions": {"allow": ["Edit(/proj/.claude/**)"]}}

