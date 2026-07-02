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

_SHIPPED_INSTALL_MYPY_INI_MJS = (
    _HOOK_DIRECTORY.parents[1] / "bin" / "install_mypy_ini.mjs"
)

_TYPESCRIPT_PATH = "src/example.ts"

_TYPESCRIPT_JSX_PATH = "src/example.tsx"


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


def _action_keyed_union_source() -> str:
    return (
        "function configureTarget(target) {\n"
        "  if (alreadyConfigured(target)) {\n"
        "    return { action: 'already-configured', path: target }\n"
        "  }\n"
        "  if (existsSync(target)) {\n"
        "    return { action: 'skipped-existing', path: target, expectedLine: expectedPathLine }\n"
        "  }\n"
        "  writeFileSync(target)\n"
        "  return { action: 'created', path: target }\n"
        "}\n"
    )


def _two_typescript_functions_with_object_return_type() -> str:
    return (
        "function alpha(): { ok: boolean } {\n"
        "  return { a: 1, b: 2 }\n"
        "}\n"
        "function beta(): { ok: boolean } {\n"
        "  return { a: 1, b: 2, c: 3 }\n"
        "}\n"
    )


def _single_typescript_function_with_drift() -> str:
    return (
        "function classify(state): { converged: boolean } {\n"
        "  if (state == null) {\n"
        "    return { converged: false, rounds: 0, blocker: 'bad state' }\n"
        "  }\n"
        "  return { converged: true, rounds: 5, blocker: null, deferred: [] }\n"
        "}\n"
    )


def _two_typescript_functions_with_named_return_type() -> str:
    return (
        "function toSummary(): UserSummary {\n"
        "  return { count: 1, size: 2 }\n"
        "}\n"
        "function toDetail(): UserDetail {\n"
        "  return { count: 3, size: 4, extra: 5 }\n"
        "}\n"
    )


def _two_typescript_functions_with_primitive_return_type() -> str:
    return (
        "function toSummary(): void {\n"
        "  return { count: 1, size: 2 }\n"
        "}\n"
        "function toDetail(): void {\n"
        "  return { count: 3, size: 4, extra: 5 }\n"
        "}\n"
    )


def _single_typescript_function_named_return_type_with_drift() -> str:
    return (
        "function classify(state): ClassifyResult {\n"
        "  if (state == null) {\n"
        "    return { converged: false, rounds: 0, blocker: 'bad state' }\n"
        "  }\n"
        "  return { converged: true, rounds: 5, blocker: null, deferred: [] }\n"
        "}\n"
    )


def _two_typescript_functions_with_function_type_return() -> str:
    return (
        "function toSummary(): (x: number) => void {\n"
        "  return { count: 1, size: 2 }\n"
        "}\n"
        "function toDetail(): (x: number) => void {\n"
        "  return { count: 3, size: 4, extra: 5 }\n"
        "}\n"
    )


def _two_typescript_functions_with_mixed_union_return() -> str:
    return (
        "function alpha(): Promise<Foo> | Bar {\n"
        "  return { x: 1, y: 2 }\n"
        "}\n"
        "function beta(): Promise<Foo> | Bar {\n"
        "  return { x: 1, y: 2, z: 3 }\n"
        "}\n"
    )


def _single_typescript_function_function_type_return_with_drift() -> str:
    return (
        "function classify(state): (x: number) => void {\n"
        "  if (state == null) {\n"
        "    return { converged: false, rounds: 0, blocker: 'bad state' }\n"
        "  }\n"
        "  return { converged: true, rounds: 5, blocker: null, deferred: [] }\n"
        "}\n"
    )


def _for_await_drift_source() -> str:
    return (
        "async function drain(stream) {\n"
        "  for await (const eachChunk of stream) {\n"
        "    if (eachChunk.bad) {\n"
        "      return { converged: false, rounds: 0, blocker: 'bad' }\n"
        "    }\n"
        "  }\n"
        "  return { converged: true, rounds: 1, blocker: null, deferred: [] }\n"
        "}\n"
    )


def _mixed_quote_shared_discriminant_drift_source() -> str:
    return (
        "function classify(state) {\n"
        "  if (state == null) {\n"
        '    return { action: "created", rounds: 0, blocker: \'bad\' }\n'
        "  }\n"
        "  return { action: 'created', rounds: 1, blocker: null, deferred: [] }\n"
        "}\n"
    )


def _mixed_quote_differing_discriminant_source() -> str:
    return (
        "function classify(state) {\n"
        "  if (state == null) {\n"
        '    return { action: "skipped-existing", rounds: 0, blocker: \'bad\' }\n'
        "  }\n"
        "  return { action: 'created', rounds: 1, blocker: null, deferred: [] }\n"
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


def test_accepts_subset_by_one_with_string_discriminant() -> None:
    issues = check_js_sibling_return_object_key_drift(_action_keyed_union_source(), _MJS_PATH)
    assert issues == []


def test_accepts_candidate_whose_supersets_disagree_on_the_missing_key() -> None:
    source = (
        "function classifyRun(state) {\n"
        "  if (state == null) {\n"
        "    return { converged: false, rounds: 0, finalSha: null }\n"
        "  }\n"
        "  if (state.failed) {\n"
        "    return { converged: false, rounds: 0, finalSha: null, failureNote: state.note }\n"
        "  }\n"
        "  return { converged: true, rounds: state.rounds, finalSha: state.sha, "
        "summary: state.summary }\n"
        "}\n"
    )
    assert check_js_sibling_return_object_key_drift(source, _MJS_PATH) == []


def test_shipped_install_mypy_ini_mjs_passes_its_own_check() -> None:
    shipped_source = _SHIPPED_INSTALL_MYPY_INI_MJS.read_text(encoding="utf-8")
    issues = check_js_sibling_return_object_key_drift(
        shipped_source, "bin/install_mypy_ini.mjs"
    )
    assert issues == []


def test_typescript_object_return_type_keeps_functions_in_separate_scopes() -> None:
    source = _two_typescript_functions_with_object_return_type()
    assert check_js_sibling_return_object_key_drift(source, _TYPESCRIPT_PATH) == []
    assert check_js_sibling_return_object_key_drift(source, _TYPESCRIPT_JSX_PATH) == []


def test_typescript_object_return_type_still_flags_intra_function_drift() -> None:
    issues = check_js_sibling_return_object_key_drift(
        _single_typescript_function_with_drift(), _TYPESCRIPT_PATH
    )
    assert len(issues) == 1
    assert "deferred" in issues[0]


def test_typescript_named_return_type_keeps_functions_in_separate_scopes() -> None:
    source = _two_typescript_functions_with_named_return_type()
    assert check_js_sibling_return_object_key_drift(source, _TYPESCRIPT_PATH) == []
    assert check_js_sibling_return_object_key_drift(source, _TYPESCRIPT_JSX_PATH) == []


def test_typescript_primitive_return_type_keeps_functions_in_separate_scopes() -> None:
    source = _two_typescript_functions_with_primitive_return_type()
    assert check_js_sibling_return_object_key_drift(source, _TYPESCRIPT_PATH) == []


def test_typescript_named_return_type_still_flags_intra_function_drift() -> None:
    issues = check_js_sibling_return_object_key_drift(
        _single_typescript_function_named_return_type_with_drift(), _TYPESCRIPT_PATH
    )
    assert len(issues) == 1
    assert "deferred" in issues[0]


def test_typescript_function_type_return_keeps_functions_in_separate_scopes() -> None:
    source = _two_typescript_functions_with_function_type_return()
    assert check_js_sibling_return_object_key_drift(source, _TYPESCRIPT_PATH) == []


def test_typescript_mixed_union_return_keeps_functions_in_separate_scopes() -> None:
    source = _two_typescript_functions_with_mixed_union_return()
    assert check_js_sibling_return_object_key_drift(source, _TYPESCRIPT_PATH) == []


def test_typescript_function_type_return_still_flags_intra_function_drift() -> None:
    issues = check_js_sibling_return_object_key_drift(
        _single_typescript_function_function_type_return_with_drift(), _TYPESCRIPT_PATH
    )
    assert len(issues) == 1
    assert "deferred" in issues[0]


def test_for_await_block_shares_its_functions_scope() -> None:
    issues = check_js_sibling_return_object_key_drift(_for_await_drift_source(), _MJS_PATH)
    assert len(issues) == 1
    assert "deferred" in issues[0]


def test_mixed_quote_shared_discriminant_does_not_suppress_drift() -> None:
    issues = check_js_sibling_return_object_key_drift(
        _mixed_quote_shared_discriminant_drift_source(), _MJS_PATH
    )
    assert len(issues) == 1
    assert "deferred" in issues[0]


def test_mixed_quote_differing_discriminant_still_passes_as_union() -> None:
    issues = check_js_sibling_return_object_key_drift(
        _mixed_quote_differing_discriminant_source(), _MJS_PATH
    )
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
