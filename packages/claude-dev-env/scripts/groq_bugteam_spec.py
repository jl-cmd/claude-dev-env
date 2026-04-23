"""Spec-mode implementer for groq_bugteam.

Splits the Claude-authored fix-spec pipeline into its own module so
groq_bugteam.py can keep the single-shot audit+fix pipeline isolated
from the mechanical patch applier. Both entrypoints share the same
HTTP client (``call_groq_with_fallback``), string helpers
(``parse_json_object``, ``preserve_trailing_newline``), and config
constants via the parent groq_bugteam module, resolved at call time
through resolve_groq_bugteam_module(). That resolver handles both
contexts: tests register the parent as ``sys.modules["groq_bugteam"]``
via spec_from_file_location, while a direct CLI invocation of
``python groq_bugteam.py --mode spec`` runs the parent as
``sys.modules["__main__"]``. The resolver also keeps tests able to
monkeypatch ``groq_bugteam.call_groq_with_fallback`` and have the
patch reach this module.

This module is imported from the bottom of groq_bugteam.py so
groq_bugteam.apply_fix_from_spec remains attribute-accessible to
existing callers and tests. The module must not import groq_bugteam
at its top level -- that would close the cycle during CLI startup
and raise ImportError before groq_bugteam_spec finishes defining its
public names.
"""

from __future__ import annotations

import json
import os
import sys
from types import ModuleType

from config.groq_bugteam_config import (
    GROQ_FIX_MAX_COMPLETION_TOKENS,
    GROQ_FIX_TEMPERATURE,
    JSON_INDENT_SPACES,
    MISSING_API_KEY_ERROR,
    PIPELINE_FAILURE_EXIT_CODE,
    REQUIRED_GROQ_BUGTEAM_ATTRIBUTES,
    SPEC_IMPLEMENTER_SYSTEM_PROMPT,
    SPEC_MODE_FLAG,
    SPEC_MODE_VALUE,
)

from groq_bugteam_dotenv import load_claude_dev_env_dotenv_file


def extract_failing_criteria_by_finding(
    acceptance_checks: list[dict],
) -> dict[int, list[str]]:
    failing_by_finding: dict[int, list[str]] = {}
    for each_check in acceptance_checks:
        if each_check.get("met"):
            continue
        each_finding_index = each_check.get("finding_index")
        if not isinstance(each_finding_index, int):
            continue
        each_criterion_text = each_check.get("criterion", "")
        failing_by_finding.setdefault(each_finding_index, []).append(
            each_criterion_text
        )
    return failing_by_finding


def demote_findings_with_failing_criteria(
    applied_finding_indexes: list[int],
    skipped_entries: list[dict],
    failing_criteria_by_finding: dict[int, list[str]],
) -> tuple[list[int], list[dict]]:
    demoted_applied = [
        each_index
        for each_index in applied_finding_indexes
        if each_index not in failing_criteria_by_finding
    ]
    already_skipped_indexes = {
        each.get("finding_index")
        for each in skipped_entries
        if each.get("finding_index") is not None
    }
    augmented_skipped = list(skipped_entries)
    for (
        each_finding_index,
        each_failing_criteria,
    ) in failing_criteria_by_finding.items():
        if each_finding_index in already_skipped_indexes:
            continue
        reason_text = "; ".join(each_failing_criteria)
        augmented_skipped.append(
            {"finding_index": each_finding_index, "reason": reason_text}
        )
    return demoted_applied, augmented_skipped


def build_spec_user_message(spec_list: list[dict], current_content: str) -> str:
    payload = {"spec": spec_list, "current_content": current_content}
    return json.dumps(payload, indent=JSON_INDENT_SPACES)


def find_missing_required_attributes(candidate_module: ModuleType) -> list[str]:
    return [
        each_attribute_name
        for each_attribute_name in REQUIRED_GROQ_BUGTEAM_ATTRIBUTES
        if not hasattr(candidate_module, each_attribute_name)
    ]


def resolve_groq_bugteam_module() -> ModuleType:
    registered_module = sys.modules.get("groq_bugteam")
    if registered_module is not None and not find_missing_required_attributes(
        registered_module
    ):
        return registered_module
    main_module = sys.modules.get("__main__")
    if main_module is not None and not find_missing_required_attributes(main_module):
        return main_module
    stub_module = registered_module if registered_module is not None else main_module
    if stub_module is not None:
        missing_attributes = find_missing_required_attributes(stub_module)
        raise RuntimeError(
            "groq_bugteam module found but missing required attributes: "
            + ", ".join(missing_attributes)
        )
    raise RuntimeError(
        "groq_bugteam module not found in sys.modules; "
        "groq_bugteam_spec must be invoked from a context where "
        "groq_bugteam is the parent module (test loader or CLI)."
    )


def coerce_to_list(candidate_value: object) -> list:
    if isinstance(candidate_value, list):
        return candidate_value
    return []


def coerce_to_string_or_fallback(
    candidate_value: object, fallback_value: str
) -> str:
    if isinstance(candidate_value, str):
        return candidate_value
    return fallback_value


def apply_fix_from_spec(spec_list: list[dict], current_content: str) -> dict:
    load_claude_dev_env_dotenv_file()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(MISSING_API_KEY_ERROR)

    groq_bugteam_module = resolve_groq_bugteam_module()
    user_message = build_spec_user_message(spec_list, current_content)
    groq_result = groq_bugteam_module.call_groq_with_fallback(
        api_key,
        messages=[
            {"role": "system", "content": SPEC_IMPLEMENTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=GROQ_FIX_TEMPERATURE,
        max_completion_tokens=GROQ_FIX_MAX_COMPLETION_TOKENS,
    )
    parsed_response = groq_bugteam_module.parse_json_object(groq_result.content)

    raw_updated_content = coerce_to_string_or_fallback(
        parsed_response.get("updated_content"), current_content
    )
    applied_finding_indexes = coerce_to_list(
        parsed_response.get("applied_finding_indexes")
    )
    skipped_entries = coerce_to_list(parsed_response.get("skipped"))
    acceptance_checks = coerce_to_list(parsed_response.get("acceptance_checks"))

    failing_criteria_by_finding = extract_failing_criteria_by_finding(acceptance_checks)
    demoted_applied, augmented_skipped = demote_findings_with_failing_criteria(
        applied_finding_indexes, skipped_entries, failing_criteria_by_finding
    )
    updated_content = groq_bugteam_module.preserve_trailing_newline(
        current_content, raw_updated_content
    )

    return {
        "updated_content": updated_content,
        "applied_finding_indexes": demoted_applied,
        "skipped": augmented_skipped,
        "acceptance_checks": acceptance_checks,
    }


def read_spec_input_from_stdin() -> tuple[list[dict], str]:
    stdin_text = sys.stdin.read()
    parsed_input = json.loads(stdin_text)
    spec_list = parsed_input.get("spec", [])
    current_content = parsed_input.get("current_content", "")
    return spec_list, current_content


def run_spec_mode() -> dict:
    try:
        spec_list, current_content = read_spec_input_from_stdin()
    except (json.JSONDecodeError, ValueError) as parse_error:
        return {"error": f"stdin is not valid JSON: {parse_error}"}
    try:
        return apply_fix_from_spec(spec_list, current_content)
    except Exception as spec_error:
        return {"error": f"spec-mode fix failed: {spec_error}"}


def is_spec_mode_invocation(argv: list[str]) -> bool:
    for each_argv_index, each_argv_token in enumerate(argv):
        if each_argv_token != SPEC_MODE_FLAG:
            continue
        if each_argv_index + 1 >= len(argv):
            continue
        if argv[each_argv_index + 1] == SPEC_MODE_VALUE:
            return True
    return False


def emit_outcome(outcome: dict) -> None:
    json.dump(outcome, sys.stdout, indent=JSON_INDENT_SPACES)
    sys.stdout.write("\n")


def run_spec_mode_main() -> None:
    spec_outcome = run_spec_mode()
    emit_outcome(spec_outcome)
    if "error" in spec_outcome:
        sys.exit(PIPELINE_FAILURE_EXIT_CODE)
