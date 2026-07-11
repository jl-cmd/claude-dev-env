"""Tests for check_js_resume_task_enumeration_coverage.

The check catches the JS/.mjs analog of the Category O6/O8
docstring-prose-vs-implementation drift: a spawn function's JSDoc enumerates
the resume tasks of its sibling resume function in a parenthetical
``(repair-verify, hardening-verify)`` list while the resume function dispatches
on a ``task === '<name>'`` branch the enumeration omits. The drift this
reproduces is PR #754: spawnVerifierAgent's JSDoc lists
``(repair-verify, hardening-verify)`` after resumeVerifierAgent gained a
``fix-verify`` branch.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SHIPPED_CONVERGE_MJS = (
    _PACKAGE_ROOT / "skills" / "autoconverge" / "workflow" / "converge.mjs"
)

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

check_js_resume_task_enumeration_coverage = (
    _imports_logging_module.check_js_resume_task_enumeration_coverage
)

_MJS_PATH = "skills/autoconverge/workflow/converge.mjs"


def _drifted_verifier_source() -> str:
    return (
        "/**\n"
        " * Spawn the verifier code-verifier agent once per converge round,\n"
        " * establishing its role so each later resume (repair-verify,\n"
        " * hardening-verify) continues the same session.\n"
        " * @returns {Promise<string|undefined>} the runtime agent id\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  if (task === 'repair-verify') {\n"
        "    return doRepair(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )


def _aligned_verifier_source() -> str:
    return _drifted_verifier_source().replace(
        "each later resume (repair-verify,\n * hardening-verify)",
        "each later resume (fix-verify, repair-verify,\n * hardening-verify)",
    )


def should_flag_resume_branch_absent_from_spawn_enumeration() -> None:
    issues = check_js_resume_task_enumeration_coverage(_drifted_verifier_source(), _MJS_PATH)
    assert len(issues) == 1
    assert "fix-verify" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_pass_when_enumeration_names_every_resume_branch() -> None:
    issues = check_js_resume_task_enumeration_coverage(_aligned_verifier_source(), _MJS_PATH)
    assert issues == []


def should_ignore_python_files() -> None:
    issues = check_js_resume_task_enumeration_coverage(
        _drifted_verifier_source(), "skills/autoconverge/workflow/converge.py"
    )
    assert issues == []


def should_ignore_spawn_jsdoc_without_resume_enumeration() -> None:
    source = (
        "/**\n"
        " * Spawn an agent with no resume enumeration in its prose.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_match_spawn_to_resume_by_role_only() -> None:
    source = (
        "/**\n"
        " * Spawn the editor so each later resume (fix-edit) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnCodeEditorAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeCodeEditorAgent(agentId, task, context) {\n"
        "  if (task === 'fix-edit') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  return doFallback(agentId, context)\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'unrelated-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_skip_test_files() -> None:
    issues = check_js_resume_task_enumeration_coverage(
        _drifted_verifier_source(), "skills/autoconverge/workflow/converge.test.mjs"
    )
    assert issues == []


def should_not_flag_single_word_task_named_in_enumeration() -> None:
    source = (
        "/**\n"
        " * Spawn the fixer so each later resume (verify-commit, commit, and\n"
        " * recovery) continues the same session.\n"
        " */\n"
        "async function spawnFixerAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeFixerAgent(agentId, task, context) {\n"
        "  if (task === 'verify-commit') {\n"
        "    return doVerify(agentId, context)\n"
        "  }\n"
        "  if (task === 'commit') {\n"
        "    return doCommit(agentId, context)\n"
        "  }\n"
        "  return doRecovery(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_flag_drift_under_oxford_comma_enumeration() -> None:
    source = (
        "/**\n"
        " * Spawn the fixer so each later resume (verify-commit, commit, and\n"
        " * recovery) continues the same session.\n"
        " */\n"
        "async function spawnFixerAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeFixerAgent(agentId, task, context) {\n"
        "  if (task === 'verify-commit') {\n"
        "    return doVerify(agentId, context)\n"
        "  }\n"
        "  if (task === 'commit') {\n"
        "    return doCommit(agentId, context)\n"
        "  }\n"
        "  if (task === 'recovery') {\n"
        "    return doRecovery(agentId, context)\n"
        "  }\n"
        "  return doBrandNewUndocumented(agentId, context)\n"
        "}\n"
    ).replace(
        "  return doBrandNewUndocumented(agentId, context)\n",
        "  if (task === 'brand-new-undocumented') {\n"
        "    return doBrandNewUndocumented(agentId, context)\n"
        "  }\n"
        "  return doRecovery(agentId, context)\n",
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "brand-new-undocumented" in issues[0]
    assert "spawnFixerAgent" in issues[0]


def should_not_overrun_into_sibling_on_unbalanced_prose_brace() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return run(agentId, 'return JSON shaped like { newSha ...')\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
        "\n"
        "/**\n"
        " * Spawn other so each later resume (stray-leak) continues the session.\n"
        " */\n"
        "async function spawnOtherAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeOtherAgent(agentId, task, context) {\n"
        "  if (task === 'stray-leak') {\n"
        "    return doStray(agentId, context)\n"
        "  }\n"
        "  return doDefault(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert issues == []


def should_not_count_task_dispatch_inside_prompt_string() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  const prompt = `when task === 'gamma-task' is set, do the thing`\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, prompt)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_flag_drift_when_task_list_follows_descriptive_parenthetical() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier on resume (re-establishing the session). Each\n"
        " * later resume (alpha-task, beta-task) continues the same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'alpha-task') {\n"
        "    return doA(agentId, context)\n"
        "  }\n"
        "  if (task === 'beta-task') {\n"
        "    return doB(agentId, context)\n"
        "  }\n"
        "  if (task === 'gamma-task') {\n"
        "    return doG(agentId, context)\n"
        "  }\n"
        "  return doDefault(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "gamma-task" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_flag_single_word_task_absent_from_mixed_enumeration() -> None:
    source = (
        "/**\n"
        " * Spawn the fixer so each later resume (verify-commit and recovery)\n"
        " * continues the same session.\n"
        " */\n"
        "async function spawnFixerAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeFixerAgent(agentId, task, context) {\n"
        "  if (task === 'verify-commit') {\n"
        "    return doVerify(agentId, context)\n"
        "  }\n"
        "  if (task === 'commit') {\n"
        "    return doCommit(agentId, context)\n"
        "  }\n"
        "  return doRecovery(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "'commit'" in issues[0]
    assert "spawnFixerAgent" in issues[0]


def should_anchor_enumeration_to_adjacent_jsdoc_only() -> None:
    source = (
        "/**\n"
        " * Earlier helper. The resume (re-entry) path is taken on retry.\n"
        " */\n"
        "function earlierHelper() {\n"
        "  return 1\n"
        "}\n"
        "\n"
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify, repair-verify,\n"
        " * hardening-verify) continues the same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  if (task === 'repair-verify') {\n"
        "    return doRepair(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_not_flag_descriptive_resume_parenthetical() -> None:
    source = (
        "/**\n"
        " * Spawn the repairer agent once per round, establishing its role so\n"
        " * each later resume (re-establishing the session) continues the same\n"
        " * conversation.\n"
        " */\n"
        "async function spawnRepairerAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeRepairerAgent(agentId, task, context) {\n"
        "  if (task === 'repair-verify') {\n"
        "    return doRepair(agentId, context)\n"
        "  }\n"
        "  return doFallback(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_not_count_task_dispatch_inside_double_quoted_string() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  const note = \"when task === 'leaked-from-dq' the agent acts\"\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, note)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_not_count_task_dispatch_inside_single_quoted_string() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  const note = 'handle the task === \"phantom\" edge'\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, note)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_still_flag_real_dispatch_after_lone_backtick_in_quoted_string() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  const note = \"use the ` char in markdown\"\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, note)\n"
        "  }\n"
        "  if (task === 'undocumented-leak') {\n"
        "    return doLeak(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "undocumented-leak" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_still_flag_real_dispatch_after_template_literal_ending_in_escaped_backslash() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  const note = `a path ending in a backslash C:\\\\`\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, note)\n"
        "  }\n"
        "  if (task === 'undocumented-leak') {\n"
        "    return doLeak(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "undocumented-leak" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_flag_dispatch_after_brace_inside_line_comment() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  } // close brace } here\n"
        "  if (task === 'phantom-comment') {\n"
        "    return doPhantom(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "phantom-comment" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_flag_dispatch_after_brace_inside_regex_literal() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  const pattern = /a}b/\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, pattern)\n"
        "  }\n"
        "  if (task === 'phantom-regex') {\n"
        "    return doPhantom(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "phantom-regex" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_flag_dispatch_after_brace_inside_block_comment() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  /* a stray brace } in a block comment */\n"
        "  if (task === 'phantom-block') {\n"
        "    return doPhantom(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "phantom-block" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_flag_dispatch_after_keyword_position_regex_with_stray_brace() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return /pat}tern/.test(context)\n"
        "  }\n"
        "  if (task === 'undocumented-leak') {\n"
        "    return doLeak(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "undocumented-leak" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_flag_dispatch_after_column_zero_function_inside_template_literal() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  const prompt = `do this:\n"
        "function notReal() { return 1 }\n"
        "then finish`\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, prompt)\n"
        "  }\n"
        "  if (task === 'undocumented-leak') {\n"
        "    return doLeak(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "undocumented-leak" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_ignore_presume_parenthetical_before_real_resume_enumeration() -> None:
    source = (
        "/**\n"
        " * We presume (alpha-beta) is fine; each later resume (fix-verify)\n"
        " * continues the same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  if (task === 'undocumented') {\n"
        "    return doUndoc(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "'undocumented'" in issues[0]
    assert "fix-verify" not in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_not_flag_single_hyphenated_word_descriptive_parenthetical() -> None:
    for each_descriptive_word in ("re-entry", "fast-forward", "pre-flight", "no-op", "auto-resume"):
        source = (
            "/**\n"
            f" * Spawn the verifier so each later resume ({each_descriptive_word})\n"
            " * continues the same session.\n"
            " */\n"
            "async function spawnVerifierAgent() {\n"
            "  return undefined\n"
            "}\n"
            "\n"
            "function resumeVerifierAgent(agentId, task, context) {\n"
            "  if (task === 'repair-verify') {\n"
            "    return doRepair(agentId, context)\n"
            "  }\n"
            "  return doHardening(agentId, context)\n"
            "}\n"
        )
        assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_flag_real_dispatch_when_false_resume_header_precedes_it_in_template_literal() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  const doc = `see function resumeVerifierAgent( ... ) below`\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  if (task === 'real-leak') {\n"
        "    return doLeak(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "real-leak" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_flag_real_dispatch_when_false_resume_header_precedes_it_in_comment() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  // function resumeVerifierAgent( is documented below\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  if (task === 'real-leak') {\n"
        "    return doLeak(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "real-leak" in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_not_count_task_substring_of_longer_identifier() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (subtask === 'phantom-sub') {\n"
        "    return doSubtask(agentId, context)\n"
        "  }\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    assert check_js_resume_task_enumeration_coverage(source, _MJS_PATH) == []


def should_still_flag_real_dispatch_alongside_task_substring_identifier() -> None:
    source = (
        "/**\n"
        " * Spawn the verifier so each later resume (fix-verify) continues the\n"
        " * same session.\n"
        " */\n"
        "async function spawnVerifierAgent() {\n"
        "  return undefined\n"
        "}\n"
        "\n"
        "function resumeVerifierAgent(agentId, task, context) {\n"
        "  if (lastTask === 'phantom-sub') {\n"
        "    return doSubtask(agentId, context)\n"
        "  }\n"
        "  if (task === 'fix-verify') {\n"
        "    return doFix(agentId, context)\n"
        "  }\n"
        "  if (task === 'real-leak') {\n"
        "    return doLeak(agentId, context)\n"
        "  }\n"
        "  return doHardening(agentId, context)\n"
        "}\n"
    )
    issues = check_js_resume_task_enumeration_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "real-leak" in issues[0]
    assert "phantom-sub" not in issues[0]
    assert "spawnVerifierAgent" in issues[0]


def should_not_flag_shipped_converge_workflow() -> None:
    converge_source = _SHIPPED_CONVERGE_MJS.read_text(encoding="utf-8")
    issues = check_js_resume_task_enumeration_coverage(
        converge_source, "skills/autoconverge/workflow/converge.mjs"
    )
    assert issues == []
