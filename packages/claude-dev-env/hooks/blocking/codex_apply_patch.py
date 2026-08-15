"""Parse Codex apply_patch commands into safe pre-edit and post-edit views."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

_codex_patch_begin_marker = "*** Begin Patch"
_codex_patch_end_marker = "*** End Patch"
_codex_update_marker = "*** Update File:"
_codex_add_marker = "*** Add File:"
_codex_delete_marker = "*** Delete File:"
_codex_hunk_marker = "@@"
_codex_end_of_file_marker = "*** End of File"
_codex_no_newline_marker = "\\ No newline at end of file"
_codex_minimum_patch_line_count = 2
_codex_update_operation = "update"
_codex_add_operation = "add"
_codex_delete_operation = "delete"


class CodexPatchError(ValueError):
    """Describe the accepted file views required by a Codex patch."""


@dataclass(frozen=True)
class CodexPatchFile:
    """Represent one Codex path with pre-edit and projected post-edit content."""

    file_path: str
    prior_content: str
    post_content: str
    operation: str


def _codex_marker_text(patch_line: str) -> str:
    """Return one patch control line minus its line ending."""
    return patch_line.rstrip("\r\n")


def _codex_resolve_patch_path(relative_path: str, working_directory: Path) -> str:
    """Resolve one relative patch path under the Codex working directory."""
    normalized_path = relative_path.replace("\\", "/")
    all_path_parts = tuple(
        each_part
        for each_part in normalized_path.split("/")
        if each_part not in ("", ".")
    )
    if (
        not all_path_parts
        or normalized_path.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized_path)
    ):
        raise CodexPatchError("patch path requires a relative location")
    if any(each_part == ".." for each_part in all_path_parts):
        raise CodexPatchError("patch path requires a traversal-free location")
    target_path = (working_directory / Path(*all_path_parts)).resolve()
    resolved_working_directory = working_directory.resolve()
    if target_path != resolved_working_directory and resolved_working_directory not in target_path.parents:
        raise CodexPatchError("patch path requires a location under the working directory")
    return str(target_path)


def _codex_patch_sections(command: str) -> list[tuple[str, str, list[str]]]:
    """Parse operation sections from a Codex apply_patch command."""
    all_lines = command.splitlines(keepends=True)
    if len(all_lines) < _codex_minimum_patch_line_count:
        raise CodexPatchError("patch requires begin and end markers")
    if _codex_marker_text(all_lines[0]) != _codex_patch_begin_marker:
        raise CodexPatchError("patch requires a begin marker")
    if _codex_marker_text(all_lines[-1]) != _codex_patch_end_marker:
        raise CodexPatchError("patch requires an end marker")
    all_sections: list[tuple[str, str, list[str]]] = []
    current_section: tuple[str, str, list[str]] | None = None
    for each_line in all_lines[1:-1]:
        marker_text = _codex_marker_text(each_line)
        operation = next(
            (
                each_operation
                for each_operation, each_marker in (
                    (_codex_update_operation, _codex_update_marker),
                    (_codex_add_operation, _codex_add_marker),
                    (_codex_delete_operation, _codex_delete_marker),
                )
                if marker_text.startswith(each_marker)
            ),
            None,
        )
        if operation is not None:
            if current_section is not None:
                all_sections.append(current_section)
            marker_by_operation = {
                _codex_update_operation: _codex_update_marker,
                _codex_add_operation: _codex_add_marker,
                _codex_delete_operation: _codex_delete_marker,
            }
            path_text = marker_text[len(marker_by_operation[operation]) :].strip()
            if not path_text:
                raise CodexPatchError("patch operation requires a path")
            current_section = (operation, path_text, [])
            continue
        if current_section is None:
            raise CodexPatchError("patch content requires a file operation")
        current_section[2].append(each_line)
    if current_section is not None:
        all_sections.append(current_section)
    if not all_sections:
        raise CodexPatchError("patch requires a file operation")
    return all_sections


def _codex_find_patch_block(
    all_current_lines: list[str], all_old_lines: list[str], search_start: int
) -> int:
    """Find one hunk's old lines at or after the prior hunk position."""
    if not all_old_lines:
        return search_start
    last_start = len(all_current_lines) - len(all_old_lines)
    for each_start in range(search_start, last_start + 1):
        if all_current_lines[each_start : each_start + len(all_old_lines)] == all_old_lines:
            return each_start
    return -1


def _codex_apply_hunk(
    all_current_lines: list[str], all_hunk_lines: list[str], search_start: int
) -> tuple[list[str], int]:
    """Apply one context, deletion, and addition hunk to file lines."""
    all_old_lines: list[str] = []
    all_new_lines: list[str] = []
    for each_line in all_hunk_lines:
        marker_text = _codex_marker_text(each_line)
        if marker_text in (_codex_end_of_file_marker, _codex_no_newline_marker):
            continue
        if not each_line or each_line[0] not in " +-":
            raise CodexPatchError("patch hunk requires context, deletion, or addition lines")
        line_content = each_line[1:]
        if each_line[0] in " -":
            all_old_lines.append(line_content)
        if each_line[0] in " +":
            all_new_lines.append(line_content)
    block_start = _codex_find_patch_block(all_current_lines, all_old_lines, search_start)
    if block_start < 0:
        raise CodexPatchError("patch hunk requires matching file content")
    all_current_lines[block_start : block_start + len(all_old_lines)] = all_new_lines
    return all_current_lines, block_start + len(all_new_lines)


def _codex_apply_update(prior_content: str, all_section_lines: list[str]) -> str:
    """Apply every hunk in one Codex update section."""
    all_current_lines = prior_content.splitlines(keepends=True)
    all_hunk_lines: list[str] = []
    search_start = 0
    has_hunk = False
    for each_line in all_section_lines:
        marker_text = _codex_marker_text(each_line)
        if marker_text.startswith(_codex_hunk_marker):
            if all_hunk_lines:
                all_current_lines, search_start = _codex_apply_hunk(
                    all_current_lines, all_hunk_lines, search_start
                )
                all_hunk_lines = []
            has_hunk = True
            continue
        all_hunk_lines.append(each_line)
    if all_hunk_lines:
        all_current_lines, _ = _codex_apply_hunk(all_current_lines, all_hunk_lines, search_start)
    if not has_hunk:
        raise CodexPatchError("update section requires a hunk marker")
    return "".join(all_current_lines)


def _codex_add_content(all_section_lines: list[str]) -> str:
    """Build new content from an Add File section."""
    all_content_lines: list[str] = []
    for each_line in all_section_lines:
        marker_text = _codex_marker_text(each_line)
        if marker_text == _codex_end_of_file_marker:
            continue
        if not each_line or each_line[0] != "+":
            raise CodexPatchError("add section requires added lines")
        all_content_lines.append(each_line[1:])
    return "".join(all_content_lines)


def _codex_read_patch_file(
    operation: str, target_path: Path, all_section_lines: list[str]
) -> CodexPatchFile:
    """Read one pre-edit file and project its post-edit content."""
    try:
        prior_content = target_path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, OSError, UnicodeDecodeError, ValueError) as error:
        if operation == _codex_add_operation and isinstance(error, FileNotFoundError):
            prior_content = ""
        else:
            raise CodexPatchError("patch target requires readable UTF-8 content") from error
    if operation == _codex_add_operation:
        if target_path.exists():
            raise CodexPatchError("add target requires a new path")
        post_content = _codex_add_content(all_section_lines)
    elif operation == _codex_update_operation:
        post_content = _codex_apply_update(prior_content, all_section_lines)
    else:
        if any(
            _codex_marker_text(each_line) != _codex_end_of_file_marker
            for each_line in all_section_lines
        ):
            raise CodexPatchError("delete section requires end-of-file content")
        post_content = ""
    return CodexPatchFile(str(target_path), prior_content, post_content, operation)


def parse_codex_apply_patch(
    command: str, working_directory: str | None = None
) -> tuple[CodexPatchFile, ...]:
    """Return pre-edit and post-edit views for every Codex patch path."""
    if not isinstance(command, str) or not command.strip():
        raise CodexPatchError("patch command requires text")
    resolved_working_directory = Path(working_directory or os.getcwd()).expanduser().resolve()
    if not resolved_working_directory.is_dir():
        raise CodexPatchError("patch working directory requires an existing directory")
    all_patch_files: list[CodexPatchFile] = []
    seen_paths: set[str] = set()
    for each_operation, each_relative_path, each_section_lines in _codex_patch_sections(command):
        try:
            resolved_path = _codex_resolve_patch_path(
                each_relative_path, resolved_working_directory
            )
        except (OSError, ValueError) as error:
            raise CodexPatchError("patch path requires a resolvable location") from error
        path_key = resolved_path.casefold()
        if path_key in seen_paths:
            raise CodexPatchError("patch paths require unique entries")
        seen_paths.add(path_key)
        all_patch_files.append(
            _codex_read_patch_file(each_operation, Path(resolved_path), each_section_lines)
        )
    return tuple(all_patch_files)
