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


def test_load_validate_content_for_full_gate_survives_a_cold_sys_modules_cache() -> None:
    """This test guards sys.modules caching, not the import path itself.

    A module the enforcer imports directly (not through the hooks_constants
    package this loader already resets) can stay cached in sys.modules from
    an earlier test in the same pytest session, so a broken import path can
    still read as working once some earlier test already imported the
    module successfully. A fresh interpreter carries no such cache.

    This does not prove the import path resolves in every layout the gate
    is loaded from -- a projected layout missing a dependency file is a
    separate failure this test cannot see, because this process still runs
    against the real repository tree where every dependency already exists
    on disk. That coverage lives in test_bugteam_code_rules_gate.py, whose
    fixture copies a deliberately narrower file set.
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
