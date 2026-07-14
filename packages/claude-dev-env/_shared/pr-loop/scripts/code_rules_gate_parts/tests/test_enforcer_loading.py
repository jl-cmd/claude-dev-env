"""Behavioral tests for the enforcer_loading parts module."""

from pathlib import Path

from code_rules_gate_parts import enforcer_loading


def test_resolve_claude_dev_env_root_finds_enforcer_bearing_root() -> None:
    resolved_root = enforcer_loading.resolve_claude_dev_env_root(Path(__file__))
    assert (resolved_root / "hooks" / "blocking" / "code_rules_enforcer.py").is_file()


def test_load_validate_content_returns_callable_passing_a_clean_module() -> None:
    validate_content = enforcer_loading.load_validate_content()
    clean_module = '"""Clean module."""\n\n\ndef ping() -> str:\n    return "pong"\n'
    issues = validate_content(clean_module, "sample.py", "")
    assert issues == []
