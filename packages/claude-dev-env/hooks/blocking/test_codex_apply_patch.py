"""Tests for the Codex apply_patch path-only target resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from codex_apply_patch import (
    CODEX_ADD_OPERATION,
    CodexPatchError,
    codex_patch_operation_targets,
)


def _three_operation_patch() -> str:
    """Build a patch naming one update, one add, and one delete section."""
    return (
        "*** Begin Patch\n"
        "*** Update File: updated.py\n"
        "@@\n"
        "-before\n"
        "+after\n"
        " keep\n"
        "*** Add File: added.py\n"
        "+new\n"
        "*** Delete File: deleted.py\n"
        "*** End of File\n"
        "*** End Patch"
    )


def test_codex_patch_operation_targets_names_every_section_without_reading_content(
    tmp_path: Path,
) -> None:
    """The path-only helper resolves every section's target without any disk read.

    Unlike ``parse_codex_apply_patch``, it never reads prior file content, so a
    caller that only needs each target path is not tripped up by an unreadable
    prior file.
    """
    all_targets = codex_patch_operation_targets(_three_operation_patch(), str(tmp_path))

    all_target_names = {
        (each_operation, str(each_path).rsplit("/", 1)[-1])
        for each_operation, each_path in all_targets
    }
    assert all_target_names == {
        ("update", "updated.py"),
        (CODEX_ADD_OPERATION, "added.py"),
        ("delete", "deleted.py"),
    }


def test_codex_patch_operation_targets_rejects_path_traversal(tmp_path: Path) -> None:
    """A patch path that escapes the working directory is rejected before any read."""
    escaping_patch = "*** Begin Patch\n*** Add File: ../outside.py\n+content\n*** End Patch"

    with pytest.raises(CodexPatchError):
        codex_patch_operation_targets(escaping_patch, str(tmp_path))
