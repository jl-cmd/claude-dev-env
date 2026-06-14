#!/usr/bin/env python3
"""CODE_RULES.md enforcer - blocks code that violates mandatory rules.

This entry module reads a PreToolUse JSON payload on stdin, reconstructs the
post-edit content, and runs every applicable check. The individual checks live
in focused ``code_rules_<concern>.py`` sibling modules; this module imports the
ones ``validate_content`` calls and orchestrates them.

Advisory only (non-blocking):
- File line count: stderr warning at 400 lines (soft) and 1000 lines (hard)

Companion tests live alongside this file as
``test_code_rules_enforcer_<suffix>.py``; the ``<suffix>`` split keeps each
concern focused. The separate ``tdd_enforcer.py`` hook accepts any
``test_code_rules_enforcer_*.py`` sibling as a test candidate for the
``code_rules_*`` module family, so the suffix files satisfy its gate.
"""
import json
import sys
from collections import Counter
from pathlib import Path
from typing import TextIO

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_annotations_length import (  # noqa: E402
    check_function_length,
    check_known_pytest_fixture_annotations,
    check_parameter_annotations,
    check_return_annotations,
)
from code_rules_banned_identifiers import (  # noqa: E402
    check_banned_identifiers,
    check_banned_noun_word_boundary,
    check_banned_prefixes,
)
from code_rules_boolean_mustcheck import (  # noqa: E402
    check_boolean_naming,
    check_ignored_must_check_return,
)
from code_rules_comments import (  # noqa: E402
    check_comment_changes,
)
from code_rules_constants_config import (  # noqa: E402
    check_constants_outside_config,
    check_constants_outside_config_advisory,
    check_file_global_constants_use_count,
)
from code_rules_dead_dataclass_field import (  # noqa: E402
    check_dead_dataclass_fields,
)
from code_rules_docstrings import (  # noqa: E402
    check_docstring_args_match_signature,
    check_docstring_format,
)
from code_rules_duplicate_body import (  # noqa: E402
    advise_cross_skill_duplicate_helper,
    check_duplicate_function_body_across_files,
)
from code_rules_imports_logging import (  # noqa: E402
    advise_file_line_count,
    check_e2e_test_naming,
    check_imports_at_top,
    check_library_print,
    check_logging_fstrings,
    check_windows_api_none,
)
from code_rules_magic_values import (  # noqa: E402
    check_fstring_structural_literals,
    check_magic_values,
)
from code_rules_mock_completeness import (  # noqa: E402
    check_incomplete_mocks,
)
from code_rules_naming_collection import (  # noqa: E402
    check_collection_prefix,
    check_loop_variable_naming,
    check_stuttering_collection_prefix,
)
from code_rules_optional_params import (  # noqa: E402
    check_duplicated_format_patterns,
    check_unused_optional_parameters,
)
from code_rules_paths_syspath import (  # noqa: E402
    check_hardcoded_user_paths,
    check_sys_path_insert_deduplication_guard,
)
from code_rules_shared import (  # noqa: E402
    changed_line_numbers,
    get_file_extension,
    is_hook_infrastructure,
    is_test_file,
)
from code_rules_string_magic import (  # noqa: E402
    check_inline_literal_collections,
    check_inline_tuple_string_magic,
    check_string_literal_magic,
)
from code_rules_test_assertions import (  # noqa: E402
    check_constant_equality_tests,
    check_existence_check_tests,
    check_skip_decorators_in_tests,
)
from code_rules_test_branching_except import (  # noqa: E402
    check_bare_except,
    check_test_branching_in_production,
)
from code_rules_test_isolation import (  # noqa: E402
    check_tests_use_isolated_filesystem_paths,
)
from code_rules_type_escape import (  # noqa: E402
    check_boundary_types,
    check_type_escape_hatches,
)
from code_rules_typeddict_stub import (  # noqa: E402
    check_stub_implementations,
    check_thin_wrapper_files,
    check_typed_dict_encode_decode,
)
from code_rules_unused_imports import (  # noqa: E402
    check_unused_module_level_imports,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_CODE_EXTENSIONS,
    ALL_JAVASCRIPT_EXTENSIONS,
    ALL_PYTHON_EXTENSIONS,
    DENY_REASON_ISSUE_PREVIEW_COUNT,
    PRECHECK_USAGE_EXIT_CODE,
    PRECHECK_USAGE_MESSAGE,
)
from hooks_constants.setup_project_paths_constants import (  # noqa: E402
    UTF8_BYTE_ORDER_MARK,
)


def validate_content(
    content: str,
    file_path: str,
    old_content: str = "",
    full_file_content: str | None = None,
    prior_full_file_content: str = "",
    defer_scope_to_caller: bool = False,
    sibling_directory: Path | None = None,
) -> list[str]:
    """Run all applicable validators on content.

    Args:
        content: The new content being written. For Edit, this is the
            ``new_string`` fragment; for Write, the entire new file body.
        file_path: Path to the file.
        old_content: Previous content (old_string for Edit, existing file for Write).
            Used to detect comment additions/removals instead of flagging all comments.
        full_file_content: For Edit operations, the reconstructed post-edit
            content of the entire file (existing file with ``old_string`` replaced
            by ``new_string``). Whole-file checks such as the unused-import
            scanner use this to evaluate references across the file rather than
            just within the inserted fragment.
        prior_full_file_content: For Edit operations, the entire file content as
            it existed before the edit applied. Whole-file span checks
            (function length, test isolation) diff this against
            ``full_file_content`` to recover the lines the edit touched, then
            block only on violations whose source span intersects those lines —
            mirroring the gate's span-intersection scoping. Defaults to the
            empty string for Write and for gate invocations, which leaves those
            checks scanning the whole file with no diff scoping.
        defer_scope_to_caller: The explicit signal that a downstream scoper will
            run, used to disambiguate the two callers that supply no changed-line
            set. The commit/push gate passes True: it owns
            ``split_violations_by_scope`` and classifies blocking vs advisory by
            added line, so the function-length, test-isolation, and banned-noun
            checks return their violations unscoped for the gate to classify.
            PreToolUse new-file or full-file writes leave this False: this
            enforcer is terminal, so it marks every violation in scope.
        sibling_directory: The absolute directory the cross-file duplicate-body
            check scans for sibling modules. The commit/push gate passes the
            resolved file's parent so the on-disk sibling scan stays anchored to
            the repository regardless of the gate process's working directory.
            None (the PreToolUse default) derives the directory from
            ``file_path``'s parent, which is already absolute on that path.
    """
    extension = get_file_extension(file_path)
    all_issues = []
    effective_content = content if full_file_content is None else full_file_content
    all_changed_lines = (
        changed_line_numbers(prior_full_file_content, full_file_content)
        if full_file_content is not None
        else None
    )

    if extension in ALL_PYTHON_EXTENSIONS:
        if not is_test_file(file_path):
            all_issues.extend(check_comment_changes(old_content, content, file_path))
        all_issues.extend(check_imports_at_top(content))
        all_issues.extend(check_logging_fstrings(content))
        all_issues.extend(check_windows_api_none(content))
        all_issues.extend(check_magic_values(content, file_path))
        all_issues.extend(check_fstring_structural_literals(content, file_path))
        all_issues.extend(check_constants_outside_config(content, file_path))
        all_issues.extend(check_constants_outside_config_advisory(content, file_path))
        all_issues.extend(check_file_global_constants_use_count(content, file_path))
        all_issues.extend(
            check_duplicate_function_body_across_files(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
                sibling_directory,
            )
        )
        all_issues.extend(check_type_escape_hatches(effective_content, file_path))
        all_issues.extend(check_banned_identifiers(content, file_path))
        all_issues.extend(
            check_banned_noun_word_boundary(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_banned_prefixes(effective_content, file_path))
        all_issues.extend(check_stub_implementations(effective_content, file_path))
        all_issues.extend(check_typed_dict_encode_decode(effective_content, file_path))
        all_issues.extend(check_test_branching_in_production(effective_content, file_path))
        all_issues.extend(check_bare_except(effective_content, file_path))
        all_issues.extend(check_thin_wrapper_files(effective_content, file_path))
        all_issues.extend(check_boundary_types(effective_content, file_path))
        all_issues.extend(check_docstring_format(effective_content, file_path))
        all_issues.extend(check_docstring_args_match_signature(effective_content, file_path))
        all_issues.extend(
            check_boolean_naming(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(
            check_ignored_must_check_return(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_skip_decorators_in_tests(content, file_path))
        all_issues.extend(
            check_tests_use_isolated_filesystem_paths(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_existence_check_tests(content, file_path))
        all_issues.extend(check_constant_equality_tests(content, file_path))
        all_issues.extend(check_unused_optional_parameters(content, file_path))
        all_issues.extend(check_collection_prefix(content, file_path))
        all_issues.extend(check_stuttering_collection_prefix(content, file_path))
        all_issues.extend(check_hardcoded_user_paths(content, file_path))
        all_issues.extend(check_sys_path_insert_deduplication_guard(content, file_path))
        all_issues.extend(
            check_unused_module_level_imports(content, file_path, full_file_content)
        )
        all_issues.extend(
            check_dead_dataclass_fields(content, file_path, full_file_content)
        )
        all_issues.extend(check_library_print(content, file_path))
        all_issues.extend(check_parameter_annotations(content, file_path))
        all_issues.extend(check_known_pytest_fixture_annotations(content, file_path))
        all_issues.extend(check_return_annotations(content, file_path))
        all_issues.extend(
            check_function_length(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_loop_variable_naming(content, file_path))
        all_issues.extend(check_inline_literal_collections(content, file_path))
        all_issues.extend(check_inline_tuple_string_magic(content, file_path))
        all_issues.extend(check_string_literal_magic(content, file_path))
        check_incomplete_mocks(content, file_path)
        check_duplicated_format_patterns(content, file_path)
        advise_cross_skill_duplicate_helper(effective_content, file_path)

    elif extension in ALL_JAVASCRIPT_EXTENSIONS:
        if not is_test_file(file_path):
            all_issues.extend(check_comment_changes(old_content, content, file_path))
        all_issues.extend(check_e2e_test_naming(content, file_path))

    if extension in ALL_CODE_EXTENSIONS:
        advise_file_line_count(content, file_path)

    return all_issues


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the on-disk content of *file_path*, or None when it cannot be read."""
    try:
        with open(file_path, "r", encoding="utf-8") as existing_file:
            return existing_file.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def prior_and_post_edit_content(
    file_path: str, old_string: str, new_string: str,
) -> tuple[str | None, str | None]:
    """Return the pre-edit and post-edit file content from a single disk read.

    Reads ``file_path`` once and derives both views from that single read so the
    prior and the reconstruction never diverge across two independent reads.
    The post-edit view replaces the first occurrence of ``old_string`` with
    ``new_string``, mirroring how the Edit tool itself applies a single
    replacement.

    Returns ``(None, None)`` when the file cannot be read, ``old_string`` is
    empty, or ``old_string`` is not present in the existing file (the Edit will
    fail or has already been applied — neither case yields a well-defined
    post-edit view). A failed prior read is never coerced to an empty string,
    because an empty prior diffs every line of the reconstruction as changed and
    defeats the diff scoping the scoped checks rely on.

    Args:
        file_path: The path of the file the Edit targets.
        old_string: The Edit's ``old_string`` fragment.
        new_string: The Edit's ``new_string`` fragment.

    Returns:
        A ``(prior_content, post_edit_content)`` pair, or ``(None, None)`` when
        no well-defined post-edit view exists.
    """
    if not old_string:
        return None, None
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        return None, None
    if old_string not in existing_content:
        return None, None
    return existing_content, existing_content.replace(old_string, new_string, 1)


def _is_validated_target(file_path: str) -> bool:
    """Return whether the path is subject to code-rules validation.

    Args:
        file_path: The destination path of the write, edit, or pre-check target.

    Returns:
        True when the path is non-empty, outside hook infrastructure, and
        carries a code extension; False for every exempt path.
    """
    if not file_path:
        return False
    if is_hook_infrastructure(file_path):
        return False
    return get_file_extension(file_path) in ALL_CODE_EXTENSIONS


def _is_hook_infrastructure_python_target(file_path: str) -> bool:
    """Return whether the path is a hook-infrastructure Python file.

    The full code-rules suite exempts hook-infrastructure files, but the
    cross-file duplicate-body check must still guard them: a helper copied
    across sibling hook modules is the exact violation it targets. This
    predicate selects the hook ``.py`` files that route to that single check.

    Args:
        file_path: The destination path of the write, edit, or pre-check target.

    Returns:
        True when the path names a Python file inside hook infrastructure.
    """
    if not file_path:
        return False
    if not is_hook_infrastructure(file_path):
        return False
    return get_file_extension(file_path) in ALL_PYTHON_EXTENSIONS


def _hook_infrastructure_duplicate_body_issues(
    content: str,
    file_path: str,
    full_file_content: str | None = None,
    prior_full_file_content: str = "",
) -> list[str]:
    """Run only the cross-file duplicate-body check for a hook Python target.

    The whole code-rules verdict stays off hook-infrastructure files, so this
    runs the single check that must still guard them, span-scoped to the lines
    an edit touched exactly as ``validate_content`` scopes it for production
    code.

    Args:
        content: The fragment or whole-file body under validation.
        file_path: The hook-infrastructure destination path.
        full_file_content: The reconstructed post-edit file body on an Edit, or
            None for a whole-file Write.
        prior_full_file_content: The file content before the edit applied, used to
            recover the changed lines on an Edit.

    Returns:
        The in-scope duplicate-body violations for the target.
    """
    effective_content = content if full_file_content is None else full_file_content
    all_changed_lines = (
        changed_line_numbers(prior_full_file_content, full_file_content)
        if full_file_content is not None
        else None
    )
    return check_duplicate_function_body_across_files(
        effective_content,
        file_path,
        all_changed_lines,
    )


def _without_line_prefix(violation_text: str) -> str:
    """Return the violation message body with its ``Line <n>: `` locator removed.

    Args:
        violation_text: A violation message, optionally carrying a leading
            ``Line <n>: `` locator.

    Returns:
        The message body shared by fragment-scoped and full-file scans of the
        same violation, regardless of which line numbering produced it.
    """
    locator, separator, message_body = violation_text.partition(": ")
    if separator and locator.startswith("Line ") and locator[len("Line "):].isdigit():
        return message_body
    return violation_text


def _forecast_full_file_violations(
    full_file_content_after_edit: str,
    file_path: str,
    prior_full_file_content: str,
    all_blocking_issues: list[str],
) -> list[str]:
    """Return full-file violations absent from the fragment-scoped blocking list.

    Runs a complete, un-scoped scan of the whole post-edit file so fragment-scoped
    checks see every line, then drops the violations already present in
    ``all_blocking_issues``. Matching is line-number-agnostic with
    per-occurrence accounting: each blocking entry consumes exactly one
    full-file entry carrying the same message body, so a violation the fragment
    itself introduces stays out of the forecast even though the two scans
    number its line differently, while a second same-message violation
    elsewhere in the file still surfaces. The remainder are the violations that
    survive elsewhere in the file and will block a future edit.

    Body matching relies on an invariant of the check suite: every check that
    embeds a secondary source position in its message body (function length,
    banned-noun binding spans, test isolation) scans the whole post-edit file
    in both passes, so those embedded positions are identical across scans;
    checks that scan only the fragment carry their position solely in the
    strippable ``Line <n>: `` locator. A fragment-scoped check that embeds a
    position in its body would defeat the dedup and re-list its own violation.

    Args:
        full_file_content_after_edit: The whole post-edit file content.
        file_path: The destination path used for classification.
        prior_full_file_content: The whole file content before the edit applied,
            used so the comment diff reflects the real prior state.
        all_blocking_issues: The fragment-scoped issues that already decide the
            deny.

    Returns:
        The full-file violations not already in ``all_blocking_issues``.
    """
    all_full_file_issues = validate_content(
        full_file_content_after_edit, file_path, prior_full_file_content
    )
    remaining_blocking_counts = Counter(
        _without_line_prefix(each_issue) for each_issue in all_blocking_issues
    )
    forecast_issues: list[str] = []
    for each_issue in all_full_file_issues:
        message_body = _without_line_prefix(each_issue)
        if remaining_blocking_counts[message_body] > 0:
            remaining_blocking_counts[message_body] -= 1
            continue
        forecast_issues.append(each_issue)
    return forecast_issues


def _precheck_hint() -> str:
    """Return the discoverability hint pointing at the script's pre-check mode."""
    script_path = str(Path(__file__).resolve())
    return (
        "; Pre-check a complete candidate before retrying: "
        f'"{sys.executable}" "{script_path}" --check <candidate> --as <target>'
    )


def _run_precheck(
    candidate_path: str,
    target_path: str,
    violation_stream: TextIO,
    error_stream: TextIO,
) -> int:
    """Validate a complete candidate file as if it lived at its destination.

    Reads the candidate's full content and runs the complete verdict (no diff
    scoping) using ``target_path`` for every path-based classification, so a
    candidate staged in a temporary directory is judged as if written to its real
    destination. Every leading byte-order mark on the candidate is stripped so
    the verdict matches the one the decoded tool-payload content receives — a
    BOM would otherwise fail AST parsing and silently skip every AST-based
    check.

    Args:
        candidate_path: The path of the candidate file to validate.
        target_path: The destination path used for extension dispatch and every
            exemption decision.
        violation_stream: The stream each violation line is written to.
        error_stream: The stream the unreadable-candidate error line is written
            to.

    Returns:
        Exit code 1 when any violation exists or the candidate cannot be read,
        and 0 when the candidate is clean or the target is exempt.
    """
    runs_full_verdict = _is_validated_target(target_path)
    runs_hook_duplicate_body = _is_hook_infrastructure_python_target(target_path)
    if not runs_full_verdict and not runs_hook_duplicate_body:
        return 0
    candidate_content = _read_existing_file_content(candidate_path)
    if candidate_content is None:
        error_stream.write(f"error: cannot read candidate file: {candidate_path}\n")
        return 1
    candidate_content = candidate_content.lstrip(UTF8_BYTE_ORDER_MARK)
    if runs_full_verdict:
        old_content = _read_existing_file_content(target_path) or ""
        all_issues = validate_content(candidate_content, target_path, old_content)
    else:
        all_issues = _hook_infrastructure_duplicate_body_issues(
            candidate_content, target_path
        )
    for each_issue in all_issues:
        violation_stream.write(f"{each_issue}\n")
    return 1 if all_issues else 0


def _precheck_arguments(all_arguments: list[str]) -> tuple[str, str] | None:
    """Parse a strict pre-check argument vector into a candidate and target pair.

    Accepts exactly the two documented shapes — ``--check <candidate>`` or
    ``--check <candidate> --as <target>`` — with the target defaulting to the
    candidate when ``--as`` is absent. Any unrecognized or extra token, a
    reordered flag, or a missing path value is rejected rather than silently
    ignored, so a malformed invocation can never look like a clean verdict.

    Args:
        all_arguments: The argument vector following the script name, expected
            to lead with ``--check``.

    Returns:
        A ``(candidate_path, target_path)`` pair for one of the two supported
        shapes; otherwise None — the vector does not lead with ``--check``,
        omits a path value, places a flag-shaped token where a path belongs,
        or carries an unrecognized or extra token.
    """
    if not all_arguments or all_arguments[0] != "--check":
        return None
    tokens_after_check = all_arguments[1:]
    if not tokens_after_check or tokens_after_check[0].startswith("--"):
        return None
    candidate_path = tokens_after_check[0]
    tokens_after_candidate = tokens_after_check[1:]
    if not tokens_after_candidate:
        return candidate_path, candidate_path
    if tokens_after_candidate[0] != "--as":
        return None
    target_tokens = tokens_after_candidate[1:]
    if len(target_tokens) != 1 or target_tokens[0].startswith("--"):
        return None
    return candidate_path, target_tokens[0]


def _run_precheck_command(
    all_arguments: list[str],
    violation_stream: TextIO,
    error_stream: TextIO,
) -> int:
    """Run the pre-check CLI mode for an argument vector carrying ``--check``.

    Args:
        all_arguments: The argument vector following the script name.
        violation_stream: The stream each violation line is written to.
        error_stream: The stream usage and candidate errors are written to.

    Returns:
        The usage-error exit code for a malformed flag sequence, otherwise the
        ``_run_precheck`` verdict for the parsed candidate and target.
    """
    precheck_paths = _precheck_arguments(all_arguments)
    if precheck_paths is None:
        error_stream.write(PRECHECK_USAGE_MESSAGE)
        return PRECHECK_USAGE_EXIT_CODE
    candidate_path, target_path = precheck_paths
    return _run_precheck(candidate_path, target_path, violation_stream, error_stream)


def _contents_for_validation(
    tool_name: str,
    new_string: str,
    old_string: str,
    written_content: str,
    file_path: str,
) -> tuple[str, str, str | None, str] | None:
    """Resolve the content views the verdict needs for the given tool payload.

    Args:
        tool_name: The tool named in the PreToolUse payload.
        new_string: The Edit payload's replacement fragment.
        old_string: The Edit payload's fragment to replace.
        written_content: The Write payload's whole file body.
        file_path: The destination path of the write or edit.

    Returns:
        A ``(content, old_content, full_file_content_after_edit,
        prior_full_file_content)`` tuple, or None when no validatable view
        exists — an unreadable edit target, or a write over an existing file.
    """
    if tool_name == "Edit":
        prior_content, full_file_content_after_edit = prior_and_post_edit_content(
            file_path, old_string, new_string,
        )
        if full_file_content_after_edit is None:
            full_file_content_after_edit = _read_existing_file_content(file_path)
            if full_file_content_after_edit is None:
                return None
        return new_string, old_string, full_file_content_after_edit, prior_content or ""
    content = written_content or new_string
    old_content = _read_existing_file_content(file_path) or ""
    if old_content:
        return None
    return content, old_content, None, ""


def _deny_reason_for_issues(
    all_blocking_issues: list[str],
    tool_name: str,
    file_path: str,
    full_file_content_after_edit: str | None,
    prior_full_file_content: str,
) -> str:
    """Compose the deny reason: blocking list, optional forecast, pre-check hint.

    Args:
        all_blocking_issues: The blocking violations that decide the deny.
        tool_name: The tool named in the PreToolUse payload.
        file_path: The destination path used for forecast classification.
        full_file_content_after_edit: The whole post-edit file content when the
            edit reconstructs one, used to run the full-file forecast.
        prior_full_file_content: The whole file content before the edit applied.
            Empty when the edit's old_string is absent and no reliable prior
            exists; the forecast is skipped in that case so a comment diff
            against an empty prior cannot mislabel pre-existing comments as
            future blockers.

    Returns:
        The complete ``permissionDecisionReason`` text.
    """
    issue_list = "; ".join(all_blocking_issues[:DENY_REASON_ISSUE_PREVIEW_COUNT])
    deny_reason = (
        f"BLOCKED: [CODE_RULES] {len(all_blocking_issues)} violation(s): {issue_list}"
    )
    has_reconstructed_prior = bool(prior_full_file_content)
    if (
        tool_name == "Edit"
        and full_file_content_after_edit is not None
        and has_reconstructed_prior
    ):
        forecast_issues = _forecast_full_file_violations(
            full_file_content_after_edit,
            file_path=file_path,
            prior_full_file_content=prior_full_file_content,
            all_blocking_issues=all_blocking_issues,
        )
        if forecast_issues:
            forecast_list = "; ".join(forecast_issues[:DENY_REASON_ISSUE_PREVIEW_COUNT])
            deny_reason += (
                f"; FULL-FILE FORECAST — {len(forecast_issues)} additional "
                "violation(s) elsewhere in this file will block future edits "
                f"(full-file line numbers): {forecast_list}"
            )
    return deny_reason + _precheck_hint()


def _write_deny_payload(deny_reason: str, deny_stream: TextIO) -> None:
    """Write a PreToolUse deny payload carrying the given reason.

    Args:
        deny_reason: The composed ``permissionDecisionReason`` text.
        deny_stream: The stream the JSON deny payload is written to.
    """
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    deny_stream.write(json.dumps(deny_payload) + "\n")
    deny_stream.flush()


def _report_blocking_violations(
    content: str,
    tool_name: str,
    file_path: str,
    old_content: str,
    full_file_content_after_edit: str | None,
    prior_full_file_content: str,
    deny_stream: TextIO,
) -> None:
    """Run the verdict and write a deny payload when blocking violations fire.

    Args:
        content: The fragment or whole-file body under validation.
        tool_name: The tool named in the PreToolUse payload.
        file_path: The destination path of the write or edit.
        old_content: The fragment the edit replaces, or empty for a write.
        full_file_content_after_edit: The reconstructed post-edit file body,
            or None when the payload is not an Edit.
        prior_full_file_content: The on-disk content before the edit.
        deny_stream: The stream the JSON deny payload is written to.
    """
    all_blocking_issues = validate_content(
        content,
        file_path,
        old_content,
        full_file_content_after_edit,
        prior_full_file_content,
    )
    if not all_blocking_issues:
        return
    _write_deny_payload(
        _deny_reason_for_issues(
            all_blocking_issues,
            tool_name,
            file_path,
            full_file_content_after_edit,
            prior_full_file_content,
        ),
        deny_stream,
    )


def _report_hook_duplicate_body(
    content: str,
    file_path: str,
    full_file_content_after_edit: str | None,
    prior_full_file_content: str,
    deny_stream: TextIO,
) -> None:
    """Write a deny payload when a hook target copies a sibling function body.

    The full code-rules verdict stays off hook-infrastructure files; this runs
    the single duplicate-body check that must still guard them and emits the deny
    payload when it fires.

    Args:
        content: The fragment or whole-file body under validation.
        file_path: The hook-infrastructure destination path.
        full_file_content_after_edit: The reconstructed post-edit file body,
            or None when the payload is not an Edit.
        prior_full_file_content: The on-disk content before the edit.
        deny_stream: The stream the JSON deny payload is written to.
    """
    all_blocking_issues = _hook_infrastructure_duplicate_body_issues(
        content,
        file_path,
        full_file_content_after_edit,
        prior_full_file_content,
    )
    if not all_blocking_issues:
        return
    issue_list = "; ".join(all_blocking_issues[:DENY_REASON_ISSUE_PREVIEW_COUNT])
    deny_reason = (
        f"BLOCKED: [CODE_RULES] {len(all_blocking_issues)} violation(s): {issue_list}"
        + _precheck_hint()
    )
    _write_deny_payload(deny_reason, deny_stream)


def main(all_arguments: list[str]) -> None:
    """Run the enforcer for the given argument vector.

    Dispatches to the pre-check CLI mode when the vector carries ``--check``;
    otherwise reads a PreToolUse payload from stdin and emits a deny payload
    on stdout when the content violates a blocking rule.

    Args:
        all_arguments: The argument vector following the script name.
    """
    if "--check" in all_arguments:
        sys.exit(_run_precheck_command(all_arguments, sys.stdout, sys.stderr))

    try:
        pretooluse_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = pretooluse_payload.get("tool_name", "")
    tool_input = pretooluse_payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    runs_full_verdict = _is_validated_target(file_path)
    if not runs_full_verdict and not _is_hook_infrastructure_python_target(file_path):
        sys.exit(0)

    validation_contents = _contents_for_validation(
        tool_name,
        tool_input.get("new_string", ""),
        tool_input.get("old_string", ""),
        tool_input.get("content", ""),
        file_path,
    )
    if validation_contents is None:
        sys.exit(0)
    content, old_content, full_file_content_after_edit, prior_full_file_content = (
        validation_contents
    )

    if not content:
        sys.exit(0)

    if not runs_full_verdict:
        _report_hook_duplicate_body(
            content,
            file_path,
            full_file_content_after_edit,
            prior_full_file_content,
            sys.stdout,
        )
        sys.exit(0)

    _report_blocking_violations(
        content,
        tool_name,
        file_path,
        old_content,
        full_file_content_after_edit,
        prior_full_file_content,
        sys.stdout,
    )
    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
