"""Tests for the Codex apply_patch adapter."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

_HOOK_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_PARENT = _HOOK_DIRECTORY.parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))
if str(_HOOKS_PARENT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_PARENT))

import code_rules_enforcer
import codex_apply_patch


def _run_codex_payload(
    payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """Run the real enforcer entry point and return its stdout."""
    monkeypatch.setattr(code_rules_enforcer.sys, "stdin", io.StringIO(json.dumps(payload)))
    with contextlib.suppress(SystemExit):
        code_rules_enforcer.main([])
    return capsys.readouterr().out


def _production_directory(tmp_path: Path) -> Path:
    """Return a temporary directory whose path carries production semantics."""
    production_directory = tmp_path.parent / "codex-prod"
    production_directory.mkdir(exist_ok=True)
    return production_directory


def test_parse_codex_apply_patch_projects_every_multi_file_operation(
    tmp_path: Path,
) -> None:
    """The parser returns pre-edit and post-edit content for update, add, and delete."""
    updated_path = tmp_path / "updated.py"
    deleted_path = tmp_path / "deleted.py"
    updated_path.write_text("before\nkeep\n", encoding="utf-8")
    deleted_path.write_text("remove\n", encoding="utf-8")
    patch = (
        "*** Begin Patch\n"
        "*** Update File: updated.py\n"
        "@@\n"
        "-before\n"
        "+after\n"
        " keep\n"
        "*** Add File: added.py\n"
        "+new\n"
        "*** Delete File: deleted.py\n"
        "*** End Patch"
    )

    all_patch_files = codex_apply_patch.parse_codex_apply_patch(patch, str(tmp_path))

    views_by_name = {
        Path(each_patch.file_path).name: each_patch for each_patch in all_patch_files
    }
    assert views_by_name["updated.py"].prior_content == "before\nkeep\n"
    assert views_by_name["updated.py"].post_content == "after\nkeep\n"
    assert views_by_name["added.py"].prior_content == ""
    assert views_by_name["added.py"].post_content == "new\n"
    assert views_by_name["deleted.py"].prior_content == "remove\n"
    assert views_by_name["deleted.py"].post_content == ""


def test_codex_payload_allows_declared_blast_radius(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A loop raise with a declared stopping scope passes the Codex hook."""
    production_directory = _production_directory(tmp_path)
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(production_directory),
        "tool_input": {
            "command": (
                "*** Begin Patch\n"
                "*** Add File: module.py\n"
                "+for each_member in all_members:\n"
                "+    raise AssetItemBlocked()\n"
                "*** End Patch"
            )
        },
    }

    stdout = _run_codex_payload(payload, monkeypatch, capsys)

    assert stdout == ""


def test_codex_payload_blocks_undeclared_blast_radius(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A loop raise requires a stopping-scope declaration for acceptance."""
    production_directory = _production_directory(tmp_path)
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(production_directory),
        "tool_input": {
            "command": (
                "*** Begin Patch\n"
                "*** Add File: module.py\n"
                "+for each_member in all_members:\n"
                "+    raise RuntimeError()\n"
                "*** End Patch"
            )
        },
    }

    stdout = _run_codex_payload(payload, monkeypatch, capsys)

    deny_payload = json.loads(stdout)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "blast radius" in deny_payload["hookSpecificOutput"]["permissionDecisionReason"]


def test_codex_payload_blocks_malformed_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A malformed Codex patch returns a blocking diagnostic."""
    production_directory = _production_directory(tmp_path)
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(production_directory),
        "tool_input": {"command": "*** Begin Patch\n*** End Patch"},
    }

    stdout = _run_codex_payload(payload, monkeypatch, capsys)

    deny_payload = json.loads(stdout)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "payload requires accepted patch markers" in deny_payload["hookSpecificOutput"]["permissionDecisionReason"]

