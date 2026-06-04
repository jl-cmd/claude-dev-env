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
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_annotations_length import (  # noqa: E402
    check_function_length,
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
from code_rules_docstrings import (  # noqa: E402
    check_docstring_args_match_signature,
    check_docstring_format,
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
)


def validate_content(
    content: str,
    file_path: str,
    old_content: str = "",
    full_file_content: str | None = None,
    prior_full_file_content: str = "",
    defer_scope_to_caller: bool = False,
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
        all_issues.extend(check_library_print(content, file_path))
        all_issues.extend(check_parameter_annotations(content, file_path))
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


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    if is_hook_infrastructure(file_path):
        sys.exit(0)

    extension = get_file_extension(file_path)
    if extension not in ALL_CODE_EXTENSIONS:
        sys.exit(0)

    old_content = ""
    prior_full_file_content = ""
    full_file_content_after_edit: str | None = None
    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
        old_content = tool_input.get("old_string", "")
        prior_content, full_file_content_after_edit = prior_and_post_edit_content(
            file_path, old_content, content,
        )
        prior_full_file_content = prior_content or ""
        if full_file_content_after_edit is None:
            full_file_content_after_edit = _read_existing_file_content(file_path)
            if full_file_content_after_edit is None:
                sys.exit(0)
    else:
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        old_content = _read_existing_file_content(file_path) or ""

        if old_content:
            sys.exit(0)

    if not content:
        sys.exit(0)

    issues = validate_content(
        content,
        file_path,
        old_content,
        full_file_content_after_edit,
        prior_full_file_content,
    )

    if issues:
        issue_list = "; ".join(issues[:10])
        deny_payload = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: [CODE_RULES] {len(issues)} violation(s): {issue_list}",
            }
        }
        print(json.dumps(deny_payload))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
