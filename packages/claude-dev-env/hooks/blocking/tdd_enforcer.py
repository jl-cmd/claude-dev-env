"""BDD Automate-phase gate (production code touch).

Blocks a write to a production source file when no matching test was modified
within the freshness window, enforcing "TDD IS NON-NEGOTIABLE" from CLAUDE.md.
A touch does not count: the gate remembers each candidate test's last-observed
content hash, so a bare mtime refresh cannot reopen it. A first sighting needs
content HEAD does not have yet, not only a fresh, real test.
Each concern lives in a ``tdd_enforcer_parts`` submodule; this entry wires them
into one PreToolUse gate and re-exports their surface for the test suite.
"""

import json
import sys
from pathlib import Path

try:
    _hooks_root_directory = str(Path(__file__).resolve().parent.parent)
    _blocking_directory = str(Path(__file__).resolve().parent)
    for each_bootstrap_directory in (_hooks_root_directory, _blocking_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from code_rules_shared import (
        is_agent_home_tooling,
        is_ephemeral_script_path,
        is_under_session_scratchpad,
    )
    from codex_apply_patch import (
        CodexPatchError,
        parse_codex_apply_patch,
        payload_patch_command,
    )
    from hooks_constants.pre_tool_use_dispatcher_constants import APPLY_PATCH_TOOL_NAME
    from tdd_enforcer_parts import (
        candidate_paths,
        content_analysis,
        content_hash_store,
        decisions,
        freshness,
        git_tracking,
        path_classification,
    )
    from tdd_enforcer_parts.config.tdd_enforcer_constants import PYTHON_SOURCE_EXTENSION
except ImportError as import_error:
    raise ImportError(
        "tdd_enforcer: cannot import its tdd_enforcer_parts submodules; "
        "ensure the hooks directory is importable."
    ) from import_error


def _apply_patch_target_file_paths(input_data: dict, tool_input: dict) -> tuple[str, ...]:
    """Return each file path a Codex apply_patch command names."""
    command, working_directory = payload_patch_command(input_data, tool_input)
    if not command:
        return ()
    try:
        all_patch_files = parse_codex_apply_patch(command, working_directory)
    except CodexPatchError:
        return ()
    return tuple(each_patch_file.file_path for each_patch_file in all_patch_files)


def _is_session_scratchpad_write(file_path: str, input_data: dict) -> bool:
    return is_under_session_scratchpad(file_path, input_data)


def _is_agent_home_tooling_write(file_path: str) -> bool:
    """A coding agent's own home-directory tooling is outside the TDD gate."""
    return is_agent_home_tooling(file_path)


production_extensions = path_classification.production_extensions
skip_extensions = path_classification.skip_extensions
_is_inside_dotclaude_segment = path_classification._is_inside_dotclaude_segment
_directory_skip_components = path_classification._directory_skip_components
_matches_any_skip_pattern = path_classification._matches_any_skip_pattern
_extract_written_content = path_classification._extract_written_content
candidate_test_paths_for = candidate_paths.candidate_test_paths_for
_ancestor_tests_directories = candidate_paths._ancestor_tests_directories
_parent_walk_limit = candidate_paths._parent_walk_limit
_freshness_seconds = freshness._freshness_seconds
_read_candidate_text = freshness._read_candidate_text
has_recorded_or_fresh_test = content_hash_store.has_recorded_or_fresh_test
_is_constants_only_python_content = content_analysis._is_constants_only_python_content
_is_post_edit_import_only = content_analysis._is_post_edit_import_only
_is_post_edit_constants_only = content_analysis._is_post_edit_constants_only
is_absent_but_tracked = git_tracking.is_absent_but_tracked
build_deny_reason = decisions.build_deny_reason
emit_allow = decisions.emit_allow
emit_deny = decisions.emit_deny


def _resolve_payload(input_data: dict) -> tuple[str, dict, str]:
    tool_input = input_data.get("tool_input", {})
    return input_data.get("tool_name", ""), tool_input, tool_input.get("file_path", "")


def _is_silently_skipped(file_path: str, extension: str, path: Path) -> bool:
    if _is_inside_dotclaude_segment(file_path) or is_ephemeral_script_path(file_path):
        return True
    if _is_agent_home_tooling_write(file_path):
        return True
    if extension in skip_extensions():
        return True
    if extension not in production_extensions():
        return True
    path_with_forward_slashes = str(path).lower().replace("\\", "/")
    return _matches_any_skip_pattern(path.name.lower(), path_with_forward_slashes)


def _edit_is_constants_or_import_only(
    tool_name: str, tool_input: dict, path: Path, extension: str
) -> bool:
    if (
        tool_name not in ("Edit", "MultiEdit")
        or extension != PYTHON_SOURCE_EXTENSION
        or not path.exists()
    ):
        return False
    existing_content = _read_candidate_text(path)
    if existing_content is None:
        return False
    if _is_post_edit_import_only(existing_content, tool_name, tool_input):
        return True
    return _is_post_edit_constants_only(existing_content, tool_name, tool_input)


def _write_is_exempt(
    tool_name: str, tool_input: dict, path: Path, extension: str
) -> bool:
    if is_absent_but_tracked(path):
        return True
    written_content = _extract_written_content(tool_name, tool_input)
    if (
        tool_name == "Write"
        and extension == PYTHON_SOURCE_EXTENSION
        and _is_constants_only_python_content(written_content)
    ):
        return True
    return _edit_is_constants_or_import_only(tool_name, tool_input, path, extension)


def _decide_for_target(
    tool_name: str, tool_input: dict, file_path: str, input_data: dict
) -> tuple[bool, str] | None:
    """Return (is_allowed, deny_reason) for one target file, or None to skip silently."""
    if not file_path:
        return None
    if _is_session_scratchpad_write(file_path, input_data):
        return None
    path = Path(file_path)
    extension = path.suffix.lower()
    if _is_silently_skipped(file_path, extension, path):
        return None
    if _write_is_exempt(tool_name, tool_input, path, extension):
        return True, ""
    all_candidates = candidate_test_paths_for(path)
    session_id = str(input_data.get("session_id") or "")
    repository_root = str(input_data.get("cwd") or "")
    is_recorded_or_fresh = has_recorded_or_fresh_test(
        all_candidates, session_id, repository_root, _freshness_seconds()
    )
    if is_recorded_or_fresh:
        return True, ""
    return False, build_deny_reason(path, all_candidates)


def _decide_apply_patch(input_data: dict, tool_input: dict) -> None:
    """Run the TDD gate over every file a Codex apply_patch payload touches."""
    for each_file_path in _apply_patch_target_file_paths(input_data, tool_input):
        decision = _decide_for_target(
            APPLY_PATCH_TOOL_NAME, tool_input, each_file_path, input_data
        )
        if decision is None:
            continue
        is_allowed, deny_reason = decision
        if not is_allowed:
            emit_deny(deny_reason)
            return
    emit_allow()


def main() -> None:
    """Run the TDD gate over one PreToolUse Write, Edit, MultiEdit, or apply_patch payload."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    tool_name, tool_input, file_path = _resolve_payload(input_data)
    if tool_name == APPLY_PATCH_TOOL_NAME:
        _decide_apply_patch(input_data, tool_input)
        sys.exit(0)
    decision = _decide_for_target(tool_name, tool_input, file_path, input_data)
    if decision is None:
        sys.exit(0)
    is_allowed, deny_reason = decision
    if is_allowed:
        emit_allow()
        sys.exit(0)
    emit_deny(deny_reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
