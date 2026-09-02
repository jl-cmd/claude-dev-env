"""Tests for subprocess_budget_completeness_content.py."""

from __future__ import annotations

import pathlib
import sys

try:
    _HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_HOOKS_ROOT) not in sys.path:
        sys.path.insert(0, str(_HOOKS_ROOT))

    from hooks_constants.subprocess_budget_completeness_content import (
        reconstructed_edit_content,
        reconstructed_multi_edit_content,
        resolved_content,
    )
except ImportError as import_error:
    raise ImportError(
        "test_subprocess_budget_completeness_content: cannot import its sibling modules; "
        "ensure the hooks directory is importable."
    ) from import_error


def test_resolved_content_returns_write_content_directly() -> None:
    assert resolved_content({"content": "abc"}) == "abc"


def test_reconstructed_edit_content_replaces_the_old_string(tmp_path: pathlib.Path) -> None:
    target_file = tmp_path / "module.py"
    target_file.write_text("value = 1\n", encoding="utf-8")
    reconstructed = reconstructed_edit_content(
        {"file_path": str(target_file), "old_string": "value = 1", "new_string": "value = 2"}
    )
    assert reconstructed == "value = 2\n"


def test_reconstructed_multi_edit_content_applies_every_edit_in_order(
    tmp_path: pathlib.Path,
) -> None:
    target_file = tmp_path / "module.py"
    target_file.write_text("a = 1\nb = 2\n", encoding="utf-8")
    all_edits = [
        {"old_string": "a = 1", "new_string": "a = 11"},
        {"old_string": "b = 2", "new_string": "b = 22"},
    ]
    reconstructed = reconstructed_multi_edit_content({"file_path": str(target_file)}, all_edits)
    assert reconstructed == "a = 11\nb = 22\n"


def test_resolved_content_dispatches_a_multi_edit_payload(tmp_path: pathlib.Path) -> None:
    target_file = tmp_path / "module.py"
    target_file.write_text("a = 1\n", encoding="utf-8")
    reconstructed = resolved_content(
        {
            "file_path": str(target_file),
            "edits": [{"old_string": "a = 1", "new_string": "a = 11"}],
        }
    )
    assert reconstructed == "a = 11\n"


def test_resolved_content_returns_empty_for_an_unreadable_edit_target(
    tmp_path: pathlib.Path,
) -> None:
    missing_target = tmp_path / "missing.py"
    assert (
        resolved_content({"file_path": str(missing_target), "old_string": "a", "new_string": "b"})
        == ""
    )


def test_reconstructed_edit_content_replaces_every_occurrence_when_replace_all_is_set(
    tmp_path: pathlib.Path,
) -> None:
    """An Edit carrying replace_all rewrites every occurrence, as the tool does.

    The MultiEdit branch has honored the flag since it moved onto apply_edits;
    the Edit branch must agree, or one payload reconstructs two ways.
    """
    target_file = tmp_path / "module.py"
    target_file.write_text("a = 1\na = 1\n", encoding="utf-8")
    reconstructed = reconstructed_edit_content(
        {
            "file_path": str(target_file),
            "old_string": "a = 1",
            "new_string": "a = 2",
            "replace_all": True,
        }
    )
    assert reconstructed == "a = 2\na = 2\n"


def test_reconstructed_edit_content_replaces_one_occurrence_without_replace_all(
    tmp_path: pathlib.Path,
) -> None:
    """Without the flag, only the first occurrence changes."""
    target_file = tmp_path / "module.py"
    target_file.write_text("a = 1\na = 1\n", encoding="utf-8")
    reconstructed = reconstructed_edit_content(
        {"file_path": str(target_file), "old_string": "a = 1", "new_string": "a = 2"}
    )
    assert reconstructed == "a = 2\na = 1\n"
