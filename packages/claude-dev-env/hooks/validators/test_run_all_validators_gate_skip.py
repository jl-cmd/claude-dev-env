"""Surface B gate-skip wiring: a new violation never downgrades to an ask.

The validators gate denies only violations the on-disk baseline does not carry.
A skip token can only escalate a block when every proposed failure is
pre-existing, so a write that introduces a fresh magic value still denies even
with a valid token in the default permission mode.
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_VALIDATORS_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent.parent / "blocking")
for each_directory in (_BLOCKING_DIRECTORY, _HOOKS_DIRECTORY, _VALIDATORS_DIRECTORY):
    if each_directory not in sys.path:
        sys.path.insert(0, each_directory)

from gate_skip_token import records  # noqa: E402
from validators.run_all_validators import (  # noqa: E402
    _decide_pre_tool_use,
    _emit_pre_tool_use_ask,
)

SESSION_ID = "gate-skip-surface-b"
CLEAN_BASELINE_SOURCE = "def clean_marker() -> int:\n    return 1\n"
NEW_MAGIC_VALUE_SOURCE = "def clean_marker() -> int:\n    return 199\n"
DEFAULT_PERMISSION_MODE = "default"


@pytest.fixture
def work_directory(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Yield a clean temp directory that holds the target and the token store.

    The validators gate copies the proposed content to a directory under the
    temp root and grades it by that copy's path, so a temp root that carries the
    test-function name would read the copy as a test file and exempt the magic
    value under test. A directory named outside that shape keeps the copy under
    full enforcement.
    """
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", "1")
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    with tempfile.TemporaryDirectory(prefix="gate_skip_surface_b_") as created_name:
        created_directory = Path(created_name)
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(created_directory))
        yield created_directory


def test_new_violation_with_token_still_denies(
    work_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target_file = work_directory / "legacy_module.py"
    target_file.write_text(CLEAN_BASELINE_SOURCE, encoding="utf-8")
    records.record_skip_token(
        SESSION_ID, str(target_file), records.content_sha256(NEW_MAGIC_VALUE_SOURCE)
    )
    _decide_pre_tool_use(
        str(target_file), NEW_MAGIC_VALUE_SOURCE, DEFAULT_PERMISSION_MODE, SESSION_ID
    )
    emitted_text = capsys.readouterr().out
    assert '"permissionDecision": "deny"' in emitted_text
    assert "Magic Values" in emitted_text


def test_emit_pre_tool_use_ask_writes_ask_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _emit_pre_tool_use_ask("only pre-existing findings remain")
    parsed_payload = json.loads(capsys.readouterr().out)
    assert parsed_payload["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert (
        parsed_payload["hookSpecificOutput"]["permissionDecisionReason"]
        == "only pre-existing findings remain"
    )
