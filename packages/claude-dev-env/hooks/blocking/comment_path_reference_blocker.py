#!/usr/bin/env python3
"""PreToolUse hook: blocks a CI-workflow comment that cites a non-resolving path.

A CI-workflow file often carries a comment that annotates test collection by
naming the collected files, written relative to the job's ``working-directory``::

    # config/tests/test_mailboxes.py (6) and tests/test_samsung_sheets.py (58)
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      ok:   config/tests/test_samsung_sheets.py   resolves under shared_utils
      flag: tests/test_samsung_sheets.py          resolves nowhere

The flagged path resolves against neither the repository root nor any
``working-directory`` the file declares, yet a file of that name lives at a
different path, so the comment misattributes where the count comes from. This hook
fires on Write, Edit, and MultiEdit targeting a ``.github/workflows`` YAML file and
blocks the write when a full-line comment cites such a path. A path that resolves,
or one whose filename exists nowhere in the tree, is left alone; for an Edit the
finding the file already held on an untouched line is excluded.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.comment_path_reference_blocker_constants import (  # noqa: E402
    ALL_NOISE_DIRECTORY_NAMES,
    ALL_REFERENCE_FILE_EXTENSIONS,
    ALL_TOKEN_PLACEHOLDER_CHARACTERS,
    ALL_WORKFLOW_FILE_EXTENSIONS,
    ALL_WRITE_EDIT_TOOL_NAMES,
    COMMA_SPACE_JOIN_SEPARATOR,
    COMMENT_LINE_PATTERN,
    GIT_DIRECTORY_NAME,
    GITHUB_WORKFLOWS_PATH_MARKER,
    MAX_SUBTREE_FILES_SCANNED,
    MAX_UNRESOLVED_ISSUES,
    NEWLINE_JOIN_SEPARATOR,
    PATH_TOKEN_PATTERN,
    UNRESOLVED_ADDITIONAL_CONTEXT,
    UNRESOLVED_MESSAGE_TEMPLATE,
    UNRESOLVED_SYSTEM_MESSAGE,
    URL_SCHEME_MARKER,
    WORKING_DIRECTORY_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.multi_edit_reconstruction import apply_edits, edits_for_tool  # noqa: E402
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin  # noqa: E402


def is_workflow_file(file_path: str) -> bool:
    """Return whether file_path names a GitHub Actions workflow YAML file.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path lies under ``.github/workflows`` and carries a YAML
        extension.
    """
    normalized_path = file_path.replace("\\", "/")
    if GITHUB_WORKFLOWS_PATH_MARKER not in normalized_path:
        return False
    _, extension = os.path.splitext(normalized_path)
    return extension.lower() in ALL_WORKFLOW_FILE_EXTENSIONS


def _resolve_scan_root(start_directory: Path) -> Path:
    """Return the repository directory whose subtree bounds the path search.

    Walks up from the workflow directory to the nearest ancestor holding a
    ``.git`` entry, so a repository-relative path resolves against the root. When
    no ancestor holds ``.git``, the start directory parent (or the start directory
    when it has no distinct parent) bounds the search.

    Args:
        start_directory: The directory that holds the target workflow file.

    Returns:
        The directory to resolve repository-relative paths against.
    """
    for each_directory in (start_directory, *start_directory.parents):
        if (each_directory / GIT_DIRECTORY_NAME).exists():
            return each_directory
    parent_directory = start_directory.parent
    if parent_directory == start_directory:
        return start_directory
    return parent_directory


def _working_directory_values(content: str) -> list[str]:
    """Return every ``working-directory`` value the workflow content declares.

    Args:
        content: The workflow file content being written.

    Returns:
        Each declared working-directory value in first-seen order with duplicates
        removed.
    """
    all_values: list[str] = []
    all_seen_values: set[str] = set()
    for each_line in content.splitlines():
        directory_match = WORKING_DIRECTORY_PATTERN.match(each_line)
        if directory_match is None:
            continue
        each_value = directory_match.group(1)
        if each_value in all_seen_values:
            continue
        all_seen_values.add(each_value)
        all_values.append(each_value)
    return all_values


def _candidate_base_directories(scan_root: Path, workflow_directory: Path, content: str) -> list[Path]:
    """Return every directory a comment path may be written relative to.

    The bases are the repository root, the workflow file's own directory, and the
    repository root joined with each declared ``working-directory`` value, since a
    GitHub Actions ``working-directory`` is relative to the workspace root.

    Args:
        scan_root: The repository root the search is bounded to.
        workflow_directory: The directory that holds the target workflow file.
        content: The workflow file content being written.

    Returns:
        The candidate base directories in resolution order.
    """
    all_bases: list[Path] = [scan_root, workflow_directory]
    for each_value in _working_directory_values(content):
        all_bases.append(scan_root / each_value)
    return all_bases


def _is_ignorable_token(path_token: str) -> bool:
    """Return whether a path token is not a repository-relative file reference.

    Args:
        path_token: A candidate path token pulled from a comment line.

    Returns:
        True when the token carries a URL scheme, a placeholder character, an
        absolute lead, or an extension outside the reference-file set.
    """
    if URL_SCHEME_MARKER in path_token or path_token.startswith("/"):
        return True
    if any(each_character in path_token for each_character in ALL_TOKEN_PLACEHOLDER_CHARACTERS):
        return True
    _, extension = os.path.splitext(path_token)
    return extension.lower() not in ALL_REFERENCE_FILE_EXTENSIONS


def _collect_comment_tokens(comment_line: str, all_tokens: list[str], all_seen_tokens: set[str]) -> None:
    """Append the kept path tokens one comment line cites to the running lists.

    Args:
        comment_line: A single line of the workflow content.
        all_tokens: The running list of kept tokens in first-seen order.
        all_seen_tokens: The set of tokens already kept, updated in place.
    """
    comment_match = COMMENT_LINE_PATTERN.match(comment_line)
    if comment_match is None:
        return
    for each_token in PATH_TOKEN_PATTERN.findall(comment_match.group(1)):
        normalized_token = each_token.lstrip("./")
        if normalized_token in all_seen_tokens or _is_ignorable_token(normalized_token):
            continue
        all_seen_tokens.add(normalized_token)
        all_tokens.append(normalized_token)


def _comment_path_tokens(content: str) -> list[str]:
    """Return each repository-relative path token cited in a full-line comment.

    Only a line whose stripped form begins with ``#`` is read, so a path inside a
    run-step command or a string value is never treated as a comment citation.

    Args:
        content: The workflow file content being written.

    Returns:
        Each candidate path token in first-seen order with duplicates removed.
    """
    all_tokens: list[str] = []
    all_seen_tokens: set[str] = set()
    for each_line in content.splitlines():
        _collect_comment_tokens(each_line, all_tokens, all_seen_tokens)
    return all_tokens


def _base_holds_file(base_directory: Path, path_token: str) -> bool:
    """Return whether joining the token to one base names an existing file.

    Args:
        base_directory: A directory the token may be written relative to.
        path_token: A repository-relative path token.

    Returns:
        True when the join names an existing file, False on absence or an OS error.
    """
    try:
        return (base_directory / path_token).is_file()
    except OSError:
        return False


def _token_resolves(path_token: str, all_base_directories: list[Path]) -> bool:
    """Return whether a path token names a file under any candidate base.

    Args:
        path_token: A repository-relative path token.
        all_base_directories: The directories the token may be written relative to.

    Returns:
        True when joining the token to any base directory names an existing file.
    """
    return any(_base_holds_file(each_base, path_token) for each_base in all_base_directories)


def _is_under_noise_directory(scan_root: Path, candidate_path: Path) -> bool:
    """Return whether candidate_path lies inside a pruned noise directory.

    Args:
        scan_root: The repository root the search descends from.
        candidate_path: A path the search yielded under the root.

    Returns:
        True when any path segment below the root names a noise directory.
    """
    try:
        all_relative_segments = candidate_path.relative_to(scan_root).parts
    except ValueError:
        all_relative_segments = candidate_path.parts
    return any(each_segment in ALL_NOISE_DIRECTORY_NAMES for each_segment in all_relative_segments)


def _filename_exists_in_tree(scan_root: Path, path_token: str) -> bool:
    """Return whether a file with the token's basename exists under the root.

    A basename that exists somewhere while the full token resolves nowhere marks
    the token as a misattributed path rather than an external reference. The walk
    prunes noise directories and stops at the scan budget.

    Args:
        scan_root: The repository root whose subtree bounds the search.
        path_token: A repository-relative path token.

    Returns:
        True when a file of that basename exists under the root, False otherwise.
    """
    target_basename = os.path.basename(path_token)
    if not target_basename:
        return False
    scanned_count = 0
    for each_match in scan_root.rglob(target_basename):
        if _is_under_noise_directory(scan_root, each_match):
            continue
        scanned_count += 1
        if scanned_count > MAX_SUBTREE_FILES_SCANNED:
            return False
        try:
            if each_match.is_file():
                return True
        except OSError:
            continue
    return False


def find_unresolved_paths(content: str, workflow_directory: Path) -> list[str]:
    """Return each comment path token that resolves nowhere yet names a real file.

    A token is a finding when it resolves against no candidate base directory while
    a file of its basename exists somewhere under the repository root. A token that
    resolves, or whose basename exists nowhere, is left alone.

    Args:
        content: The workflow file content being written.
        workflow_directory: The directory that holds the target workflow file.

    Returns:
        Each unresolved path token in first-seen order, capped at the issue budget.
    """
    scan_root = _resolve_scan_root(workflow_directory)
    all_base_directories = _candidate_base_directories(scan_root, workflow_directory, content)
    unresolved_paths: list[str] = []
    for each_token in _comment_path_tokens(content):
        if _token_resolves(each_token, all_base_directories):
            continue
        if not _filename_exists_in_tree(scan_root, each_token):
            continue
        unresolved_paths.append(each_token)
        if len(unresolved_paths) >= MAX_UNRESOLVED_ISSUES:
            break
    return unresolved_paths


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the current on-disk content of file_path, or None when unreadable.

    Args:
        file_path: The path of the file the edit targets.

    Returns:
        The file text, or None when the file is missing or cannot be decoded.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _joined_edit_fragments(all_edits: list[dict]) -> str:
    """Return the MultiEdit replacement fragments joined into one scannable block.

    Args:
        all_edits: The MultiEdit ``edits`` list.

    Returns:
        The joined replacement text, empty when no fragment is a non-empty string.
    """
    kept_fragments = [
        each_edit.get("new_string", "")
        for each_edit in all_edits
        if isinstance(each_edit, dict)
        and isinstance(each_edit.get("new_string", ""), str)
        and each_edit.get("new_string", "")
    ]
    return NEWLINE_JOIN_SEPARATOR.join(kept_fragments)


def _candidate_content_and_baseline(
    tool_name: str, tool_input: dict, file_path: str, workflow_directory: Path
) -> tuple[str | None, set[str]]:
    """Return the content to scan and the findings the file already held.

    For Write the candidate is the full new content with no baseline, so every
    finding it names is introduced. For Edit and MultiEdit the candidate is the
    existing file with the replacements applied, and the baseline is the finding
    set the existing file already held. When the existing file cannot be read, the
    joined new_string fragments are scanned with no baseline.

    Args:
        tool_name: The intercepted tool, one of Write, Edit, MultiEdit.
        tool_input: The tool input payload.
        file_path: The destination path of the write or edit.
        workflow_directory: The directory that holds the target workflow file.

    Returns:
        The candidate content to scan paired with the baseline finding set.
    """
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return (content if isinstance(content, str) and content else None, set())
    all_edits = edits_for_tool(tool_name, tool_input)
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        joined_fragments = _joined_edit_fragments(all_edits)
        return (joined_fragments or None, set())
    baseline_findings = set(find_unresolved_paths(existing_content, workflow_directory))
    return (apply_edits(existing_content, all_edits), baseline_findings)


def _build_block_payload(all_unresolved_paths: list[str], file_path: str) -> dict:
    """Build the PreToolUse deny payload listing each unresolved path.

    Args:
        all_unresolved_paths: The path tokens to report.
        file_path: The destination path of the workflow file.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    formatted_paths = COMMA_SPACE_JOIN_SEPARATOR.join("`" + each_path + "`" for each_path in all_unresolved_paths)
    reason = UNRESOLVED_MESSAGE_TEMPLATE.format(file=file_path, paths=formatted_paths)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": UNRESOLVED_ADDITIONAL_CONTEXT,
        },
        "systemMessage": UNRESOLVED_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def _emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    """Write the hook result JSON to the given output stream.

    Args:
        all_hook_data: The hook-result dictionary to serialize.
        output_stream: The stream the harness reads the decision from.
    """
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


def _extract_target(input_data: dict) -> tuple[str, dict, str] | None:
    """Return the tool name, input, and file path when the call is in scope.

    Args:
        input_data: The parsed PreToolUse payload.

    Returns:
        The tool name, tool input, and target file path when the intercepted tool
        is a write targeting a workflow YAML file, or None otherwise.
    """
    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str) or tool_name not in ALL_WRITE_EDIT_TOOL_NAMES:
        return None
    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_workflow_file(file_path):
        return None
    return tool_name, tool_input, file_path


def _report_block(all_unresolved_paths: list[str], file_path: str, tool_name: str) -> None:
    """Log and emit the deny decision for the unresolved comment paths.

    Args:
        all_unresolved_paths: The path tokens to report.
        file_path: The destination path of the workflow file.
        tool_name: The intercepted tool name.
    """
    block_payload = _build_block_payload(all_unresolved_paths, file_path)
    log_hook_block(
        calling_hook_name="comment_path_reference_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    _emit_hook_result(block_payload, sys.stdout)


def main() -> None:
    """Read the PreToolUse payload from stdin and block a non-resolving comment path."""
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)
    target = _extract_target(input_data)
    if target is None:
        sys.exit(0)
    tool_name, tool_input, file_path = target
    workflow_directory = Path(file_path).resolve().parent
    if not workflow_directory.is_dir():
        sys.exit(0)
    candidate_content, baseline_findings = _candidate_content_and_baseline(
        tool_name, tool_input, file_path, workflow_directory
    )
    if candidate_content is None:
        sys.exit(0)
    unresolved_paths = [
        each_path
        for each_path in find_unresolved_paths(candidate_content, workflow_directory)
        if each_path not in baseline_findings
    ]
    if unresolved_paths:
        _report_block(unresolved_paths, file_path, tool_name)
    sys.exit(0)


if __name__ == "__main__":
    main()
