"""Tests for the stale_comment_reference_blocker hook."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

_BLOCKING_DIR = str(Path(__file__).resolve().parent)
_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIR not in sys.path:
    sys.path.insert(0, _BLOCKING_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)

from stale_comment_reference_blocker import (  # noqa: E402
    build_deny_payload,
    evaluate,
)

from hooks_constants.hook_block_logger import _HOOK_BLOCKS_LOG_RELATIVE_PATH  # noqa: E402

HOOK_SCRIPT_PATH = str(Path(__file__).resolve().parent / "stale_comment_reference_blocker.py")

PATCHED_SLEEP_LINE = (
    "    with patch('theme_exports.core.exporter.asyncio.sleep', new_callable=AsyncMock):\n"
)
PATCHED_POLL_LINE = "    with patch('theme_exports.core.exporter.wait_for_overlay_clear', new_callable=AsyncMock):\n"
KEPT_COMMENT_LINE = "    # Mock asyncio\n"


def _run_hook(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_module(tmp_path: Path, source_text: str) -> Path:
    written_module_path = tmp_path / "sample_module.py"
    written_module_path.write_text(source_text, encoding="utf-8")
    return written_module_path


def test_blocks_edit_that_orphans_the_comment_above(tmp_path: Path) -> None:
    """Rewriting the patched target under an unchanged comment naming it
    is denied.
    """
    written_module_path = _write_module(
        tmp_path,
        "def launch_export() -> None:\n" + KEPT_COMMENT_LINE + PATCHED_SLEEP_LINE,
    )
    outcome = _run_hook(
        "Edit",
        {
            "file_path": str(written_module_path),
            "old_string": PATCHED_SLEEP_LINE.rstrip("\n"),
            "new_string": PATCHED_POLL_LINE.rstrip("\n"),
        },
    )
    assert outcome.returncode == 0
    decision = json.loads(outcome.stdout)
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "asyncio" in decision["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_edit_that_updates_the_comment_together(tmp_path: Path) -> None:
    """An edit rewriting the comment and the line together passes."""
    written_module_path = _write_module(
        tmp_path,
        "def launch_export() -> None:\n" + KEPT_COMMENT_LINE + PATCHED_SLEEP_LINE,
    )
    outcome = _run_hook(
        "Edit",
        {
            "file_path": str(written_module_path),
            "old_string": KEPT_COMMENT_LINE + PATCHED_SLEEP_LINE,
            "new_string": "    # Mock the overlay poll\n" + PATCHED_POLL_LINE,
        },
    )
    assert outcome.returncode == 0
    assert outcome.stdout == ""


def test_allows_edit_that_keeps_the_named_identifier(tmp_path: Path) -> None:
    """A rewrite that still carries the identifier the comment names passes."""
    written_module_path = _write_module(
        tmp_path,
        "def launch_export() -> None:\n" + KEPT_COMMENT_LINE + PATCHED_SLEEP_LINE,
    )
    retained_line = "    with patch('theme_exports.core.exporter.asyncio.sleep'):\n"
    outcome = _run_hook(
        "Edit",
        {
            "file_path": str(written_module_path),
            "old_string": PATCHED_SLEEP_LINE.rstrip("\n"),
            "new_string": retained_line.rstrip("\n"),
        },
    )
    assert outcome.returncode == 0
    assert outcome.stdout == ""


def test_allows_prose_comment_with_no_orphaned_identifier(tmp_path: Path) -> None:
    """A prose comment whose tokens never name anything in the edited line
    passes.
    """
    written_module_path = _write_module(
        tmp_path,
        "def launch_export() -> None:\n"
        "    # Overlay settle pause\n"
        "    runner.pause_for_overlay_settle()\n",
    )
    outcome = _run_hook(
        "Edit",
        {
            "file_path": str(written_module_path),
            "old_string": "    runner.pause_for_overlay_settle()",
            "new_string": "    runner.confirm_editor_ready()",
        },
    )
    assert outcome.returncode == 0
    assert outcome.stdout == ""


def test_allows_non_python_file(tmp_path: Path) -> None:
    """A non-Python target passes untouched."""
    plain_text_target = tmp_path / "notes.txt"
    plain_text_target.write_text("# Mock asyncio\nasyncio row\n", encoding="utf-8")
    outcome = _run_hook(
        "Edit",
        {
            "file_path": str(plain_text_target),
            "old_string": "asyncio row",
            "new_string": "other row",
        },
    )
    assert outcome.returncode == 0
    assert outcome.stdout == ""


def test_allows_write_tool() -> None:
    """A non-Edit invocation passes untouched."""
    outcome = _run_hook(
        "Write",
        {
            "file_path": "src/sample_module.py",
            "content": KEPT_COMMENT_LINE + PATCHED_POLL_LINE,
        },
    )
    assert outcome.returncode == 0
    assert outcome.stdout == ""


def test_allows_missing_file(tmp_path: Path) -> None:
    """An Edit aimed at a path with no readable target passes."""
    outcome = _run_hook(
        "Edit",
        {
            "file_path": str(tmp_path / "absent_module.py"),
            "old_string": "one",
            "new_string": "two",
        },
    )
    assert outcome.returncode == 0
    assert outcome.stdout == ""


def test_allows_old_string_not_found(tmp_path: Path) -> None:
    """An Edit whose old_string never occurs in the target passes."""
    written_module_path = _write_module(tmp_path, "value_count = 1\n")
    outcome = _run_hook(
        "Edit",
        {
            "file_path": str(written_module_path),
            "old_string": "never present",
            "new_string": "still never present",
        },
    )
    assert outcome.returncode == 0
    assert outcome.stdout == ""


def test_deny_payload_logs_the_block(tmp_path: Path) -> None:
    """One record lands in the block journal for each denial built through
    evaluate plus build_deny_payload.
    """
    written_module_path = _write_module(
        tmp_path,
        "def launch_export() -> None:\n" + KEPT_COMMENT_LINE + PATCHED_SLEEP_LINE,
    )
    deny_reason = evaluate(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(written_module_path),
                "old_string": PATCHED_SLEEP_LINE.rstrip("\n"),
                "new_string": PATCHED_POLL_LINE.rstrip("\n"),
            },
        }
    )
    assert deny_reason is not None
    with patch.object(Path, "home", return_value=tmp_path):
        deny_payload = build_deny_payload(deny_reason)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    block_log_path = tmp_path / _HOOK_BLOCKS_LOG_RELATIVE_PATH
    all_log_records = block_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(all_log_records) == 1
    parsed_log_line = json.loads(all_log_records[0])
    assert parsed_log_line["hook"] == "stale_comment_reference_blocker.py"
