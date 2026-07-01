"""Tests for check_js_returns_object_schemaless_branch.

The check catches the JS/.mjs Category O6 docstring-prose-vs-implementation
drift PR #807 surfaced: a ``function`` whose JSDoc ``@returns {Promise<object>}``
promises a structured object, while one branch returns the agent-spawn helper
with an options object that omits ``schema``. A schema-less agent call resolves
to a transcript string, not the object the JSDoc claims, so the contract drifts
for that branch while a sibling branch that does pass ``schema`` returns a real
object.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_module_spec = importlib.util.spec_from_file_location(
    "code_rules_imports_logging",
    _HOOK_DIRECTORY / "code_rules_imports_logging.py",
)
assert _module_spec is not None
assert _module_spec.loader is not None
_imports_logging_module = importlib.util.module_from_spec(_module_spec)
_module_spec.loader.exec_module(_imports_logging_module)

check_js_returns_object_schemaless_branch = (
    _imports_logging_module.check_js_returns_object_schemaless_branch
)

_MJS_PATH = "skills/autoconverge/workflow/converge.mjs"

_SHIPPED_CONVERGE_MJS = (
    _HOOK_DIRECTORY.parents[1] / "skills" / "autoconverge" / "workflow" / "converge.mjs"
)


def _mixed_schema_source() -> str:
    return (
        "/**\n"
        " * Spawn a git-utility agent for a task.\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runGitTask(task, head) {\n"
        "  if (task === 'resolve-head') {\n"
        "    return convergeAgent(\n"
        "      `Print the HEAD SHA of ${prCoordinates}.`,\n"
        "      { label: 'git-utility', phase: 'Converge', schema: HEAD_SCHEMA, agentType: 'Explore' },\n"
        "    )\n"
        "  }\n"
        "  if (task === 'prefetch-main') {\n"
        "    return convergeAgent(\n"
        "      `Refresh the base ref for ${prCoordinates}.`,\n"
        "      { label: 'git-utility', phase: 'Converge', agentType: 'Explore' },\n"
        "    )\n"
        "  }\n"
        "  return convergeAgent(\n"
        "    `Report conflicts for ${prCoordinates}.`,\n"
        "    { label: 'git-utility', phase: 'Converge', schema: MERGE_CONFLICT_SCHEMA, agentType: 'Explore' },\n"
        "  )\n"
        "}\n"
    )


def _all_schema_source() -> str:
    return _mixed_schema_source().replace(
        "      { label: 'git-utility', phase: 'Converge', agentType: 'Explore' },\n",
        "      { label: 'git-utility', phase: 'Converge', schema: FETCH_SCHEMA, agentType: 'Explore' },\n",
    )


def _plain_object_return_source() -> str:
    return (
        "/**\n"
        " * Joined fixer recovery loop.\n"
        " * @returns {Promise<object>} FIX_SCHEMA result\n"
        " */\n"
        "async function fixerWithRecovery(head, findings, sourceLabel) {\n"
        "  if (!verdictPassed) {\n"
        "    return {\n"
        "      newSha: head,\n"
        "      pushed: false,\n"
        "      summary: `verify step did not pass ${sourceLabel}`,\n"
        "    }\n"
        "  }\n"
        "  return commitWithRecovery({\n"
        "    runCommit: () => runFixerTask('commit', { head }),\n"
        "    runVerify: () => runVerifierTask('fix-verify', { head }),\n"
        "  })\n"
        "}\n"
    )


def _transcript_typed_source() -> str:
    return _mixed_schema_source().replace(
        " * @returns {Promise<object>} the structured output\n",
        " * @returns {Promise<*>} the agent() result\n",
    )


def _destructured_parameter_mixed_schema_source() -> str:
    return (
        "/**\n"
        " * Commit and verify with recovery.\n"
        " * @returns {Promise<object>} the structured verify output\n"
        " */\n"
        "async function commitWithRecovery({ runCommit, runVerify, head }) {\n"
        "  if (runVerify) {\n"
        "    return convergeAgent(\n"
        "      `Verify the commit for ${head}.`,\n"
        "      { label: 'commit-recovery', phase: 'Converge', schema: VERIFY_SCHEMA, agentType: 'Explore' },\n"
        "    )\n"
        "  }\n"
        "  return convergeAgent(\n"
        "    `Commit ${head} without verification.`,\n"
        "    { label: 'commit-recovery', phase: 'Converge', agentType: 'Explore' },\n"
        "  )\n"
        "}\n"
    )


def test_flags_schema_less_branch_under_returns_object_claim() -> None:
    issues = check_js_returns_object_schemaless_branch(_mixed_schema_source(), _MJS_PATH)
    assert len(issues) == 1
    assert "runGitTask" in issues[0]
    assert "convergeAgent" in issues[0]


def test_flags_schema_less_branch_with_destructured_parameter() -> None:
    issues = check_js_returns_object_schemaless_branch(
        _destructured_parameter_mixed_schema_source(), _MJS_PATH
    )
    assert len(issues) == 1
    assert "commitWithRecovery" in issues[0]
    assert "convergeAgent" in issues[0]


def test_accepts_function_when_every_branch_passes_a_schema() -> None:
    issues = check_js_returns_object_schemaless_branch(_all_schema_source(), _MJS_PATH)
    assert issues == []


def test_accepts_plain_object_returns_with_no_schema_driven_helper() -> None:
    issues = check_js_returns_object_schemaless_branch(_plain_object_return_source(), _MJS_PATH)
    assert issues == []


def test_accepts_transcript_typed_returns_clause() -> None:
    issues = check_js_returns_object_schemaless_branch(_transcript_typed_source(), _MJS_PATH)
    assert issues == []


def test_skips_python_files() -> None:
    issues = check_js_returns_object_schemaless_branch(
        _mixed_schema_source(), "workflow/converge.py"
    )
    assert issues == []


def test_shipped_converge_mjs_passes_its_own_check() -> None:
    shipped_source = _SHIPPED_CONVERGE_MJS.read_text(encoding="utf-8")
    issues = check_js_returns_object_schemaless_branch(shipped_source, _MJS_PATH)
    assert issues == []
