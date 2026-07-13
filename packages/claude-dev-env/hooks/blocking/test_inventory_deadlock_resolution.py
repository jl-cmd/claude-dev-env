"""End-to-end tests for the inventory/orphan pending-intent deadlock resolution.

Each test drives the two real hook binaries through their production ``main()``
stdin path over a temp directory tree whose ``CLAUDE.md`` inventory names two
sibling files. A shared ``session_id`` and an isolated ``TMPDIR`` make the two
hooks read one shared intent-records file, so a deny by one hook opens the gate
for the sibling's second write — in either add order.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BLOCKING_DIRECTORY = Path(__file__).resolve().parent

INVENTORY_HOOK = "package_inventory_stale_blocker.py"
ORPHAN_HOOK = "claude_md_orphan_file_blocker.py"

SESSION_ID = "deadlock-session"

INVENTORY_TABLE_HEADER = "# pkg\n\n| File | Purpose |\n|---|---|\n"
ALPHA_ROW = "| `alpha.py` | Does A |\n"
BETA_ROW = "| `beta.py` | Does B |\n"
GAMMA_ROW = "| `gamma.py` | Does G |\n"
EPSILON_ROW = "| `epsilon.py` | Does E |\n"

BASE_INVENTORY = INVENTORY_TABLE_HEADER + ALPHA_ROW + BETA_ROW
INVENTORY_WITH_GAMMA = BASE_INVENTORY + GAMMA_ROW
INVENTORY_WITH_EPSILON = BASE_INVENTORY + EPSILON_ROW

MODULE_BODY = "x = 1\n"


def _package_directory(tmp_path: Path) -> Path:
    """Return a package directory holding a CLAUDE.md table naming two siblings."""
    package_directory = tmp_path / "pkg"
    package_directory.mkdir()
    (package_directory / "CLAUDE.md").write_text(BASE_INVENTORY, encoding="utf-8")
    (package_directory / "alpha.py").write_text(MODULE_BODY, encoding="utf-8")
    (package_directory / "beta.py").write_text(MODULE_BODY, encoding="utf-8")
    return package_directory


def _run_hook(
    hook_filename: str, tool_name: str, tool_input: dict, temp_directory: Path
) -> subprocess.CompletedProcess:
    """Run one hook binary over a payload, sharing an isolated intent-records store."""
    payload = json.dumps(
        {"tool_name": tool_name, "tool_input": tool_input, "session_id": SESSION_ID}
    )
    hook_environment = dict(os.environ)
    hook_environment["TMPDIR"] = str(temp_directory)
    return subprocess.run(
        [sys.executable, str(BLOCKING_DIRECTORY / hook_filename)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        env=hook_environment,
    )


def _decision(completed: subprocess.CompletedProcess) -> str | None:
    """Return the permission decision a hook emitted, or None when it allowed."""
    if not completed.stdout.strip():
        return None
    return json.loads(completed.stdout)["hookSpecificOutput"]["permissionDecision"]


def _reason(completed: subprocess.CompletedProcess) -> str:
    """Return the deny reason a hook emitted."""
    return json.loads(completed.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


def test_file_first_order_resolves_after_one_deny(tmp_path: Path) -> None:
    package_directory = _package_directory(tmp_path)
    new_file = package_directory / "gamma.py"
    claude_md = package_directory / "CLAUDE.md"

    first_write = _run_hook(
        INVENTORY_HOOK, "Write", {"file_path": str(new_file), "content": MODULE_BODY}, tmp_path
    )
    assert _decision(first_write) == "deny"
    assert "gamma.py" in _reason(first_write)
    assert "recorded" in _reason(first_write)

    row_write = _run_hook(
        ORPHAN_HOOK,
        "Write",
        {"file_path": str(claude_md), "content": INVENTORY_WITH_GAMMA},
        tmp_path,
    )
    assert _decision(row_write) is None

    claude_md.write_text(INVENTORY_WITH_GAMMA, encoding="utf-8")
    retry_write = _run_hook(
        INVENTORY_HOOK, "Write", {"file_path": str(new_file), "content": MODULE_BODY}, tmp_path
    )
    assert _decision(retry_write) is None


def test_row_first_order_resolves_after_one_deny(tmp_path: Path) -> None:
    package_directory = _package_directory(tmp_path)
    new_file = package_directory / "gamma.py"
    claude_md = package_directory / "CLAUDE.md"

    first_row = _run_hook(
        ORPHAN_HOOK,
        "Write",
        {"file_path": str(claude_md), "content": INVENTORY_WITH_GAMMA},
        tmp_path,
    )
    assert _decision(first_row) == "deny"
    assert "gamma.py" in _reason(first_row)
    assert "recorded" in _reason(first_row)

    file_write = _run_hook(
        INVENTORY_HOOK, "Write", {"file_path": str(new_file), "content": MODULE_BODY}, tmp_path
    )
    assert _decision(file_write) is None

    new_file.write_text(MODULE_BODY, encoding="utf-8")
    retry_row = _run_hook(
        ORPHAN_HOOK,
        "Write",
        {"file_path": str(claude_md), "content": INVENTORY_WITH_GAMMA},
        tmp_path,
    )
    assert _decision(retry_row) is None


def test_new_file_with_no_row_attempt_stays_blocked(tmp_path: Path) -> None:
    package_directory = _package_directory(tmp_path)
    new_file = package_directory / "delta.py"
    file_write = _run_hook(
        INVENTORY_HOOK, "Write", {"file_path": str(new_file), "content": MODULE_BODY}, tmp_path
    )
    assert _decision(file_write) == "deny"
    assert "delta.py" in _reason(file_write)


def test_row_naming_uncreated_file_stays_blocked(tmp_path: Path) -> None:
    package_directory = _package_directory(tmp_path)
    claude_md = package_directory / "CLAUDE.md"
    row_write = _run_hook(
        ORPHAN_HOOK,
        "Write",
        {"file_path": str(claude_md), "content": INVENTORY_WITH_EPSILON},
        tmp_path,
    )
    assert _decision(row_write) == "deny"
    assert "epsilon.py" in _reason(row_write)
