"""Enforcer-dispatch tests for the JS returns-object schema-less branch check.

These drive ``validate_content`` end-to-end on a ``.mjs`` payload, so they prove
the check is wired into the JavaScript branch of the enforcer, not just callable
in isolation. The drift: a ``function`` whose JSDoc ``@returns {Promise<object>}``
promises a structured object while one branch returns the agent helper with an
options object that omits ``schema`` and so resolves to a transcript string.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()

_MJS_PATH = "skills/autoconverge/workflow/converge.mjs"


def _mixed_schema_mjs() -> str:
    return (
        "/**\n"
        " * Spawn a git-utility agent.\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runGitTask(task, head) {\n"
        "  if (task === 'resolve-head') {\n"
        "    return convergeAgent(`head ${x}`, { label: 'g', schema: HEAD_SCHEMA, agentType: 'Explore' })\n"
        "  }\n"
        "  return convergeAgent(`fetch ${x}`, { label: 'g', agentType: 'Explore' })\n"
        "}\n"
    )


def _all_schema_mjs() -> str:
    return _mixed_schema_mjs().replace(
        "{ label: 'g', agentType: 'Explore' })",
        "{ label: 'g', schema: FETCH_SCHEMA, agentType: 'Explore' })",
    )


def _has_returns_object_finding(all_issues: list[str]) -> bool:
    return any("runGitTask" in each_issue and "@returns" in each_issue for each_issue in all_issues)


def test_enforcer_reports_schema_less_branch_under_returns_object() -> None:
    drift_source = _mixed_schema_mjs()
    all_issues = code_rules_enforcer.validate_content(drift_source, _MJS_PATH, drift_source)
    assert _has_returns_object_finding(all_issues)


def test_enforcer_accepts_every_branch_with_a_schema() -> None:
    clean_source = _all_schema_mjs()
    all_issues = code_rules_enforcer.validate_content(clean_source, _MJS_PATH, clean_source)
    assert not _has_returns_object_finding(all_issues)
