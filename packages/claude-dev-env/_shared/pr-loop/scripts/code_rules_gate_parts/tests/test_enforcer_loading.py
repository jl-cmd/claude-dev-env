"""Behavioral tests for the enforcer_loading parts module."""

import subprocess
import sys
from pathlib import Path

from code_rules_gate_parts import enforcer_loading

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[2]


def test_resolve_claude_dev_env_root_finds_enforcer_bearing_root() -> None:
    resolved_root = enforcer_loading.resolve_claude_dev_env_root(Path(__file__))
    assert (resolved_root / "hooks" / "blocking" / "code_rules_enforcer.py").is_file()


def test_load_validate_content_for_full_gate_returns_callable_passing_a_clean_module() -> None:
    validate_content = enforcer_loading.load_validate_content_for_full_gate()
    clean_module = '"""Clean module."""\n\n\ndef ping() -> str:\n    return "pong"\n'
    issues = validate_content(clean_module, "sample.py", "")
    assert issues == []


def test_load_validate_content_for_full_gate_succeeds_in_a_fresh_process() -> None:
    """The gate's own loading path imports cleanly with no leaked sys.modules cache.

    A module the enforcer imports directly (not through the hooks_constants
    package this loader already resets) can stay cached in sys.modules from an
    earlier test in the same pytest session, papering over a bad import path.
    A fresh interpreter has no such cache, so this is how the root suite and
    a real push actually exercise the load.
    """
    probe_script = (
        "from code_rules_gate_parts.enforcer_loading import "
        "load_validate_content_for_full_gate\n"
        "load_validate_content_for_full_gate()\n"
        "print('ENFORCER_LOAD_OK')\n"
    )
    completed_process = subprocess.run(
        [sys.executable, "-c", probe_script],
        cwd=str(_SCRIPTS_DIRECTORY),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed_process.returncode == 0, completed_process.stderr
    assert "ENFORCER_LOAD_OK" in completed_process.stdout
