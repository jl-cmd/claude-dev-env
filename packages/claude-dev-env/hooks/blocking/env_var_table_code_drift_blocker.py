#!/usr/bin/env python3
"""PreToolUse hook: blocks a markdown env-var table that names a non-reading code file.

A documentation file often carries a "Summary: Environment Variables" table whose
rows pair an environment variable with the code file that reads it, written as
``| `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | ... |``. When that
code file exists under the repository yet its source never references the
variable name, the row is stale: the table claims a consumer relationship the
code does not have, so a reader trusts the doc to a behavior the code lost. This
hook fires on Write, Edit, and MultiEdit targeting a ``.md`` file and blocks the
write when a row attributes a variable to a code file that exists yet does not
read it. A row whose code file cannot be resolved under the scan root is left
alone (the hook cannot prove the drift), and for an Edit the drift the file
already held on an untouched row is excluded so only drift the edit introduces is
reported.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.env_var_table_code_drift_constants import (  # noqa: E402
    ALL_CODE_FILE_EXTENSIONS,
    ALL_NOISE_DIRECTORY_NAMES,
    BACKTICK_TOKEN_PATTERN,
    CODE_FENCE_PATTERN,
    DRIFT_ADDITIONAL_CONTEXT,
    DRIFT_MESSAGE_TEMPLATE,
    DRIFT_SYSTEM_MESSAGE,
    ENV_VAR_NAME_PATTERN,
    GIT_DIRECTORY_NAME,
    MARKDOWN_FILE_EXTENSION,
    MAX_DRIFT_ISSUES,
    MAX_SUBTREE_FILES_SCANNED,
    MINIMUM_ENV_VAR_ROW_CELL_COUNT,
    SEPARATOR_CELL_PATTERN,
    TABLE_ROW_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.multi_edit_reconstruction import (  # noqa: E402
    apply_edits,
    edits_for_tool,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def is_markdown_file(file_path: str) -> bool:
    """Return whether file_path names a markdown file.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path extension is ``.md`` (case-insensitive).
    """
    _, extension = os.path.splitext(file_path)
    return extension.lower() == MARKDOWN_FILE_EXTENSION


def _row_cells(table_line: str) -> list[str]:
    """Return the trimmed cells of one markdown table row.

    Args:
        table_line: A single line that begins with a pipe character.

    Returns:
        The text of each pipe-delimited cell, stripped, with the empty leading
        and trailing segments a bounding pipe produces removed.
    """
    stripped_line = table_line.strip()
    inner = stripped_line.strip("|")
    return [each_cell.strip() for each_cell in inner.split("|")]


def _first_backtick_token(cell_text: str) -> str | None:
    """Return the first backtick-wrapped token in a cell, when it has one.

    Args:
        cell_text: The trimmed text of a table cell.

    Returns:
        The text inside the first pair of backticks, or None when the cell
        carries no backtick-wrapped token.
    """
    token_match = BACKTICK_TOKEN_PATTERN.search(cell_text)
    if token_match is None:
        return None
    inner_text = token_match.group(1).strip()
    return inner_text or None


def _env_var_name_in_cell(cell_text: str) -> str | None:
    """Return the environment-variable name a cell names, when it names one.

    Args:
        cell_text: The trimmed text of a table cell.

    Returns:
        The UPPER_SNAKE variable name inside the first backticks, or None when
        the cell names no variable-shaped token.
    """
    token = _first_backtick_token(cell_text)
    if token is None:
        return None
    if ENV_VAR_NAME_PATTERN.match(token) is None:
        return None
    return token


def _code_file_reference_in_cell(cell_text: str) -> str | None:
    """Return the code-file path a cell names, when it names one.

    Args:
        cell_text: The trimmed text of a table cell.

    Returns:
        The relative code-file path inside the first backticks, or None when the
        token carries no recognized code-file extension.
    """
    token = _first_backtick_token(cell_text)
    if token is None:
        return None
    _, extension = os.path.splitext(token)
    if extension.lower() not in ALL_CODE_FILE_EXTENSIONS:
        return None
    return token


def _is_separator_row(all_cells: list[str]) -> bool:
    """Return whether every cell is a markdown table header-separator cell.

    Args:
        all_cells: The trimmed cells of one table row.

    Returns:
        True when each cell holds only dashes, colons, and whitespace.
    """
    return all(SEPARATOR_CELL_PATTERN.match(each_cell) is not None for each_cell in all_cells)


def _resolve_scan_root(markdown_directory: Path) -> Path:
    """Return the repository directory whose subtree bounds the code-file search.

    Walks up from the markdown directory to the nearest ancestor holding a
    ``.git`` entry, so a relative code path resolves against the repository root.
    When no ancestor holds ``.git``, the markdown directory parent (or the
    directory itself when it has no distinct parent) bounds the search.

    Args:
        markdown_directory: The directory that holds the target markdown file.

    Returns:
        The directory to walk when resolving a referenced code file.
    """
    for each_directory in (markdown_directory, *markdown_directory.parents):
        if (each_directory / GIT_DIRECTORY_NAME).exists():
            return each_directory
    parent_directory = markdown_directory.parent
    if parent_directory == markdown_directory:
        return markdown_directory
    return parent_directory


def _is_under_noise_directory(scan_root: Path, candidate_path: Path) -> bool:
    """Return whether candidate_path lies inside a pruned noise directory.

    Args:
        scan_root: The directory the walk descends from.
        candidate_path: A path the walk yielded under the scan root.

    Returns:
        True when any path segment below scan_root names a noise directory.
    """
    try:
        relative_segments = candidate_path.relative_to(scan_root).parts
    except ValueError:
        relative_segments = candidate_path.parts
    return any(each_segment in ALL_NOISE_DIRECTORY_NAMES for each_segment in relative_segments)


def _resolve_code_file(scan_root: Path, code_reference: str) -> Path | None:
    """Return the on-disk code file a row reference names, when one resolves.

    Resolves the relative reference against the scan root first; when that exact
    path is absent, searches the subtree for a file whose path ends with the
    referenced segments, so ``auth/google_auth.py`` resolves under a nested
    package. A match inside a noise directory is pruned.

    Args:
        scan_root: The directory whose subtree bounds the search.
        code_reference: The relative code-file path a table row names.

    Returns:
        The resolved code file, or None when no file matches under the scan root.
    """
    normalized_reference = code_reference.replace("\\", "/").lstrip("/")
    direct_path = scan_root / normalized_reference
    if direct_path.is_file():
        return direct_path
    reference_basename = os.path.basename(normalized_reference)
    if not reference_basename:
        return None
    suffix_marker = "/" + normalized_reference
    scanned_count = 0
    for each_match in scan_root.rglob(reference_basename):
        if _is_under_noise_directory(scan_root, each_match):
            continue
        scanned_count += 1
        if scanned_count > MAX_SUBTREE_FILES_SCANNED:
            return None
        try:
            if not each_match.is_file():
                continue
        except OSError:
            continue
        match_text = "/" + str(each_match).replace("\\", "/")
        if match_text.endswith(suffix_marker):
            return each_match
    return None


def _code_file_reads_variable(code_file: Path, variable_name: str) -> bool | None:
    """Return whether a code file source references variable_name.

    Args:
        code_file: The resolved on-disk code file.
        variable_name: The environment-variable name to look for.

    Returns:
        True when the file text contains the variable name, False when it does
        not, and None when the file cannot be read.
    """
    try:
        source_text = code_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return variable_name in source_text


def find_drift_rows(content: str, markdown_directory: Path) -> list[str]:
    """Return each env-var table row whose code file does not read the variable.

    Walks the markdown content line by line, skipping lines inside a fenced code
    block. A table row counts when its first cell names an UPPER_SNAKE variable and
    a later cell names a code file with a recognized extension. The row drifts when
    that code file resolves under the scan root yet its source never references the
    variable name; a row whose code file does not resolve, or cannot be read, is
    left alone. Each finding is rendered as ``VARIABLE -> code/path``.

    Args:
        content: The markdown content being written.
        markdown_directory: The directory that holds the target markdown file.

    Returns:
        Each drifted row in first-seen order with duplicates removed, capped at
        the issue budget.
    """
    scan_root = _resolve_scan_root(markdown_directory)
    drift_rows: list[str] = []
    already_reported: set[str] = set()
    is_inside_code_fence = False
    for each_line in content.splitlines():
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            continue
        if is_inside_code_fence:
            continue
        if TABLE_ROW_PATTERN.match(each_line) is None:
            continue
        each_finding = _drift_finding_for_row(each_line, scan_root)
        if each_finding is None or each_finding in already_reported:
            continue
        already_reported.add(each_finding)
        drift_rows.append(each_finding)
        if len(drift_rows) >= MAX_DRIFT_ISSUES:
            break
    return drift_rows


def _drift_finding_for_row(table_line: str, scan_root: Path) -> str | None:
    """Return the drift finding one table row produces, when it drifts.

    Args:
        table_line: A single markdown table row.
        scan_root: The directory whose subtree bounds the code-file search.

    Returns:
        A ``VARIABLE -> code/path`` finding when the code file resolves yet does
        not read the variable, or None otherwise.
    """
    all_cells = _row_cells(table_line)
    if len(all_cells) < MINIMUM_ENV_VAR_ROW_CELL_COUNT or _is_separator_row(all_cells):
        return None
    variable_name = _env_var_name_in_cell(all_cells[0])
    if variable_name is None:
        return None
    for each_cell in all_cells[1:]:
        code_reference = _code_file_reference_in_cell(each_cell)
        if code_reference is None:
            continue
        code_file = _resolve_code_file(scan_root, code_reference)
        if code_file is None:
            return None
        reads_variable = _code_file_reads_variable(code_file, variable_name)
        if reads_variable is None or reads_variable:
            return None
        return variable_name + " -> " + code_reference
    return None


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

    Each ``new_string`` value present as a non-empty string is kept, in list
    order, and the kept fragments are joined with newlines so the resulting text
    carries every table row the edit introduces. Used as the scan fallback when
    the existing file cannot be read.

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
    return "\n".join(kept_fragments)


def _candidate_content_and_baseline(
    tool_name: str, tool_input: dict, file_path: str, markdown_directory: Path
) -> tuple[str | None, set[str]]:
    """Return the content to scan and the drift the file already held.

    For Write the candidate is the full new content with no baseline, so every
    drift it names is introduced. For Edit and MultiEdit the candidate is the
    existing file with the replacements applied, and the baseline is the drift the
    existing file already held, so a pre-existing drift on an untouched row is
    excluded. When the existing file cannot be read, the joined new_string
    fragments are scanned with no baseline.

    Args:
        tool_name: The intercepted tool, one of Write, Edit, MultiEdit.
        tool_input: The tool input payload.
        file_path: The destination path of the write or edit.
        markdown_directory: The directory that holds the target markdown file.

    Returns:
        The candidate content to scan paired with the baseline drift set.
    """
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return (content if isinstance(content, str) and content else None, set())
    all_edits = edits_for_tool(tool_name, tool_input)
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        joined_fragments = _joined_edit_fragments(all_edits)
        return (joined_fragments or None, set())
    baseline_drift = set(find_drift_rows(existing_content, markdown_directory))
    return (apply_edits(existing_content, all_edits), baseline_drift)


def _build_block_payload(all_drift_rows: list[str], file_path: str) -> dict:
    """Build the PreToolUse deny payload listing each drifted row.

    Args:
        all_drift_rows: The VARIABLE -> code/path findings to report.
        file_path: The destination path of the markdown file.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    formatted_drift = ", ".join("`" + each_row + "`" for each_row in all_drift_rows)
    reason = DRIFT_MESSAGE_TEMPLATE.format(file=file_path, drift=formatted_drift)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": DRIFT_ADDITIONAL_CONTEXT,
        },
        "systemMessage": DRIFT_SYSTEM_MESSAGE,
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


def main() -> None:
    """Read the PreToolUse payload from stdin and block a drifted env-var table."""
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str) or tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_markdown_file(file_path):
        sys.exit(0)

    markdown_directory = Path(file_path).resolve().parent
    if not markdown_directory.is_dir():
        sys.exit(0)

    candidate_content, baseline_drift = _candidate_content_and_baseline(
        tool_name, tool_input, file_path, markdown_directory
    )
    if candidate_content is None:
        sys.exit(0)

    drift_rows = [
        each_row
        for each_row in find_drift_rows(candidate_content, markdown_directory)
        if each_row not in baseline_drift
    ]
    if not drift_rows:
        sys.exit(0)

    block_payload = _build_block_payload(drift_rows, file_path)
    log_hook_block(
        calling_hook_name="env_var_table_code_drift_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
