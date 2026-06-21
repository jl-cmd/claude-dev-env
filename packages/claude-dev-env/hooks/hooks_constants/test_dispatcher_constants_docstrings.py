"""Regression tests proving the dispatcher constants docstrings clear the O6 gate.

The PreToolUse and PostToolUse dispatcher constants modules each carry a module
docstring stating what the module centralizes. Neither docstring may assert that
no literals appear inline in its companion dispatcher script — that completeness
claim about a sibling file is the deterministic Category O6 drift the enforcer's
check_docstring_no_inline_literal_claim blocks. These tests load the real
modules' source and assert the check returns no issues for either.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    enforcer_path = Path(__file__).resolve().parent.parent / "blocking" / "code_rules_enforcer.py"
    enforcer_spec = importlib.util.spec_from_file_location("code_rules_enforcer", enforcer_path)
    assert enforcer_spec is not None
    assert enforcer_spec.loader is not None
    enforcer_module = importlib.util.module_from_spec(enforcer_spec)
    enforcer_spec.loader.exec_module(enforcer_module)
    return enforcer_module


code_rules_enforcer = _load_enforcer_module()


def _check_issues_for(module_filename: str) -> list[str]:
    module_path = Path(__file__).resolve().parent / module_filename
    module_source = module_path.read_text(encoding="utf-8")
    return code_rules_enforcer.check_docstring_no_inline_literal_claim(
        module_source, str(module_path)
    )


def test_pre_tool_use_dispatcher_constants_docstring_clears_o6_gate() -> None:
    assert _check_issues_for("pre_tool_use_dispatcher_constants.py") == []


def test_post_tool_use_dispatcher_constants_docstring_clears_o6_gate() -> None:
    assert _check_issues_for("post_tool_use_dispatcher_constants.py") == []
