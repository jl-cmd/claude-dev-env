"""Tests for check_js_sibling_return_object_key_drift.

The check catches the JS/.mjs Category O return-shape drift PR #824 surfaced: a
workflow body whose success return carries a field (``allDeferredPrs``) while a
blocker early-return in the same scope omits it. The two return paths disagree on
shape, so an orchestrator reading the field off the blocker result gets undefined
where the documented contract and the sibling return both promise it. Early exits
that omit two or more fields — a genuinely smaller exit shape — pass.
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

check_js_sibling_return_object_key_drift = (
    _imports_logging_module.check_js_sibling_return_object_key_drift
)

_MJS_PATH = "skills/autoconverge/workflow/converge_multi.mjs"

_SHIPPED_CONVERGE_MJS = (
    _HOOK_DIRECTORY.parents[1] / "skills" / "autoconverge" / "workflow" / "converge.mjs"
)


def _multi_workflow_source(blocker_return_body: str) -> str:
    return (
        "function classifyMultiInput(rawArgs) {\n"
        "  if (rawArgs == null) {\n"
        "    return { input: null, blocker: 'bad coordinates' }\n"
        "  }\n"
        "  return { input: rawArgs, blocker: null }\n"
        "}\n"
        "\n"
        "const multiInput = classifyMultiInput(args)\n"
        "if (multiInput.blocker) {\n"
        f"  {blocker_return_body}\n"
        "}\n"
        "const input = multiInput.input\n"
        "\n"
        "const childResults = await parallel(\n"
        "  input.prs.map((eachPr) => async () => {\n"
        "    return {\n"
        "      owner: eachPr.owner,\n"
        "      repo: eachPr.repo,\n"
        "      prNumber: eachPr.prNumber,\n"
        "      converged: true,\n"
        "      deferredPrs: [],\n"
        "    }\n"
        "  }),\n"
        ")\n"
        "\n"
        "return {\n"
        "  converged: true,\n"
        "  prCount: input.prs.length,\n"
        "  convergedCount: input.prs.length,\n"
        "  results: childResults,\n"
        "  allDeferredPrs: [],\n"
        "  blocker: null,\n"
        "}\n"
    )


def _drifted_blocker_source() -> str:
    return _multi_workflow_source(
        "return { converged: false, prCount: 0, convergedCount: 0, results: [], "
        "blocker: multiInput.blocker }"
    )


def _consistent_blocker_source() -> str:
    return _multi_workflow_source(
        "return { converged: false, prCount: 0, convergedCount: 0, results: [], "
        "allDeferredPrs: [], blocker: multiInput.blocker }"
    )


def _three_field_gap_source() -> str:
    return (
        "const runInput = classifyRunInput(args)\n"
        "if (runInput.blocker) {\n"
        "  return { converged: false, rounds: 0, finalSha: null, blocker: runInput.blocker }\n"
        "}\n"
        "\n"
        "return {\n"
        "  converged: true,\n"
        "  rounds,\n"
        "  finalSha: head,\n"
        "  blocker: null,\n"
        "  standardsNote,\n"
        "  copilotNote,\n"
        "  reuseNote,\n"
        "}\n"
    )


def _cross_scope_subset_source() -> str:
    return (
        "function buildFull() {\n"
        "  return { alpha: 1, beta: 2, gamma: 3 }\n"
        "}\n"
        "\n"
        "function buildPartial() {\n"
        "  return { alpha: 1, beta: 2 }\n"
        "}\n"
    )


def _discriminated_union_source() -> str:
    return (
        "function classifyOutcome(state) {\n"
        "  if (state == null) return { kind: 'retry' }\n"
        "  if (state.done === true) return { kind: 'ready', summary: state.summary }\n"
        "  return { kind: 'repair', failures: state.failures }\n"
        "}\n"
    )


def test_flags_blocker_return_that_omits_one_documented_field() -> None:
    issues = check_js_sibling_return_object_key_drift(_drifted_blocker_source(), _MJS_PATH)
    assert len(issues) == 1
    assert "allDeferredPrs" in issues[0]


def test_accepts_when_blocker_return_carries_the_field() -> None:
    issues = check_js_sibling_return_object_key_drift(_consistent_blocker_source(), _MJS_PATH)
    assert issues == []


def test_accepts_early_exit_that_omits_more_than_one_field() -> None:
    issues = check_js_sibling_return_object_key_drift(_three_field_gap_source(), _MJS_PATH)
    assert issues == []


def test_scopes_subset_comparison_to_a_single_function() -> None:
    issues = check_js_sibling_return_object_key_drift(_cross_scope_subset_source(), _MJS_PATH)
    assert issues == []


def test_accepts_discriminated_union_returns() -> None:
    issues = check_js_sibling_return_object_key_drift(_discriminated_union_source(), _MJS_PATH)
    assert issues == []


def test_skips_python_files() -> None:
    issues = check_js_sibling_return_object_key_drift(
        _drifted_blocker_source(), "workflow/converge_multi.py"
    )
    assert issues == []


def test_shipped_converge_mjs_passes_its_own_check() -> None:
    shipped_source = _SHIPPED_CONVERGE_MJS.read_text(encoding="utf-8")
    issues = check_js_sibling_return_object_key_drift(shipped_source, _MJS_PATH)
    assert issues == []
