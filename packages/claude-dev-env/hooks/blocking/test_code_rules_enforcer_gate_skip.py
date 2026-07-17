"""Surface A gate-skip wiring: the enforcer downgrades a deadlock deny to an ask.

A file that already carries a banned-prefix function is the deadlock: an Edit to
an unrelated clean line elsewhere still trips the banned-prefix finding, so the
write can never pass by refactoring the touched line alone. Under the default
permission mode, with a valid skip token and no new finding, the enforcer
escalates that deny to a human permission ``ask`` and consumes the token once.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

import code_rules_enforcer  # noqa: E402
from code_rules_enforcer import _finding_identity  # noqa: E402
from gate_skip_token import records  # noqa: E402

SESSION_ID = "gate-skip-surface-a"
BANNED_PREFIX_FILE_SOURCE = (
    "def handle_thing(payload: str) -> str:\n"
    "    return payload\n"
    "\n"
    "def compute_total(first_number: int, second_number: int) -> int:\n"
    "    return first_number + second_number\n"
)
CLEAN_LINE_OLD = "    return first_number + second_number\n"
CLEAN_LINE_NEW = "    running_sum = first_number + second_number\n    return running_sum\n"
NEW_VIOLATION_OLD = "def compute_total(first_number: int, second_number: int) -> int:\n"
NEW_VIOLATION_NEW = "def process_data(first_number: int, second_number: int) -> int:\n"
DEFAULT_PERMISSION_MODE = "default"
ACCEPT_EDITS_PERMISSION_MODE = "acceptEdits"


@pytest.fixture
def work_directory(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Yield a clean temp directory that holds both the target and the token store.

    A pytest ``tmp_path`` carries the test-function name, and that name matches
    the test-file path shape, so a target under it reads as a test file and the
    banned-prefix check is exempted. A directory named outside that shape keeps
    the target under full enforcement. The same directory backs the token store
    so a recorded token and the enforcer's lookup share one location.
    """
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", "1")
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    with tempfile.TemporaryDirectory(prefix="gate_skip_surface_a_") as created_name:
        created_directory = Path(created_name)
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(created_directory))
        yield created_directory


def _edit_payload(target_file: Path, old_string: str, new_string: str, permission_mode: str) -> str:
    """Return one Edit PreToolUse payload as JSON text."""
    return json.dumps(
        {
            "tool_name": "Edit",
            "permission_mode": permission_mode,
            "session_id": SESSION_ID,
            "tool_input": {
                "file_path": str(target_file),
                "old_string": old_string,
                "new_string": new_string,
            },
        }
    )


def _run_edit(
    payload_text: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str | None:
    """Drive the enforcer for one payload and return its permission decision.

    Args:
        payload_text: The Edit PreToolUse payload as JSON text.
        monkeypatch: The fixture used to redirect the enforcer's stdin.
        capsys: The fixture used to capture the emitted payload on stdout.

    Returns:
        The ``permissionDecision`` string, or None when the enforcer emits nothing.
    """
    monkeypatch.setattr(code_rules_enforcer.sys, "stdin", io.StringIO(payload_text))
    try:
        code_rules_enforcer.main([])
    except SystemExit:
        pass
    emitted_text = capsys.readouterr().out
    if not emitted_text.strip():
        return None
    return json.loads(emitted_text)["hookSpecificOutput"]["permissionDecision"]


def _record_token_for(target_file: Path, old_string: str, new_string: str) -> None:
    """Record a skip token bound to the whole post-edit body of one Edit."""
    on_disk_content = target_file.read_text(encoding="utf-8")
    proposed_content = on_disk_content.replace(old_string, new_string, 1)
    records.record_skip_token(
        SESSION_ID, str(target_file), records.content_sha256(proposed_content)
    )


def test_deadlock_edit_without_token_denies(
    work_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target_file = work_directory / "orders.py"
    target_file.write_text(BANNED_PREFIX_FILE_SOURCE, encoding="utf-8")
    payload_text = _edit_payload(
        target_file, CLEAN_LINE_OLD, CLEAN_LINE_NEW, DEFAULT_PERMISSION_MODE
    )
    assert _run_edit(payload_text, monkeypatch, capsys) == "deny"


def test_default_mode_with_token_asks_then_consumes_the_token(
    work_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target_file = work_directory / "orders.py"
    target_file.write_text(BANNED_PREFIX_FILE_SOURCE, encoding="utf-8")
    _record_token_for(target_file, CLEAN_LINE_OLD, CLEAN_LINE_NEW)
    payload_text = _edit_payload(
        target_file, CLEAN_LINE_OLD, CLEAN_LINE_NEW, DEFAULT_PERMISSION_MODE
    )
    assert _run_edit(payload_text, monkeypatch, capsys) == "ask"
    assert _run_edit(payload_text, monkeypatch, capsys) == "deny"


def test_accept_edits_mode_with_token_denies(
    work_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target_file = work_directory / "orders.py"
    target_file.write_text(BANNED_PREFIX_FILE_SOURCE, encoding="utf-8")
    _record_token_for(target_file, CLEAN_LINE_OLD, CLEAN_LINE_NEW)
    payload_text = _edit_payload(
        target_file, CLEAN_LINE_OLD, CLEAN_LINE_NEW, ACCEPT_EDITS_PERMISSION_MODE
    )
    assert _run_edit(payload_text, monkeypatch, capsys) == "deny"


def test_new_violation_with_token_still_denies(
    work_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target_file = work_directory / "orders.py"
    target_file.write_text(BANNED_PREFIX_FILE_SOURCE, encoding="utf-8")
    _record_token_for(target_file, NEW_VIOLATION_OLD, NEW_VIOLATION_NEW)
    payload_text = _edit_payload(
        target_file, NEW_VIOLATION_OLD, NEW_VIOLATION_NEW, DEFAULT_PERMISSION_MODE
    )
    assert _run_edit(payload_text, monkeypatch, capsys) == "deny"


def test_finding_identity_normalizes_line_numbers() -> None:
    early_line_finding = "Line 12: Function 'handle_thing' uses banned prefix"
    later_line_finding = "Line 405: Function 'handle_thing' uses banned prefix"
    assert _finding_identity(early_line_finding) == _finding_identity(later_line_finding)
    assert "12" not in _finding_identity(early_line_finding)
