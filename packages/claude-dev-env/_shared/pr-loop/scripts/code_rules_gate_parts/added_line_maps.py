"""Map each changed file to the line numbers the current diff added.

::

    one combined ``git diff --unified=0 --no-renames``
        -> split on ``diff --git`` headers
        -> {relative_posix: {added line numbers}}
    path missing from that map -> per-file diff fallback
    rename destination         -> blob-to-blob diff vs source

The gate scopes each violation to those added lines, including whole-file spans
for brand-new files and only the true additions on a rename.
"""

import codecs
import subprocess
import sys
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_GIT_DIFF_CACHED_UNIFIED_ZERO_NO_RENAMES_COMMAND,
    ALL_GIT_DIFF_UNIFIED_ZERO_NO_RENAMES_COMMAND_PREFIX,
    DIFF_GIT_HEADER_PREFIX,
    EXPECTED_NON_RENAME_COLUMN_COUNT,
    EXPECTED_RENAME_COLUMN_COUNT,
    GIT_C_STYLE_ESCAPE_BACKSLASH,
    GIT_C_STYLE_ESCAPE_ENCODING,
    GIT_C_STYLE_LATIN1_ENCODING,
    GIT_DIFF_DESTINATION_PATH_PREFIX,
    GIT_DIFF_PATH_ARGUMENT_SEPARATOR,
    GIT_DIFF_SOURCE_PATH_PREFIX,
    GIT_NAME_STATUS_RENAMED_PREFIX,
    GIT_PATH_UTF8_ENCODING,
    GIT_QUOTED_PATH_DELIMITER,
)
from terminology_sweep import repository_environment

from code_rules_gate_parts.git_file_sets import (
    _git_bytes_or_exit,
    _git_text_or_exit,
    resolve_merge_base,
)
from code_rules_gate_parts.violation_scoping import parse_added_line_numbers


def _run_git_text_capture(
    repository_root: Path, all_git_arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    """Run a git command in text mode and return the completed process."""
    return subprocess.run(
        all_git_arguments,
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=repository_environment(),
    )


def _decode_git_c_style_escapes(escaped_path_text: str) -> str:
    """Decode a git C-style escape sequence into a UTF-8 path string.

    ::

        in:  \\303\\251.py
        out: é.py

    Args:
        escaped_path_text: Path text that may hold ``\\`` octal escapes.

    Returns:
        The decoded UTF-8 path string.
    """
    decoded_latin1 = codecs.decode(escaped_path_text, GIT_C_STYLE_ESCAPE_ENCODING)
    return decoded_latin1.encode(GIT_C_STYLE_LATIN1_ENCODING).decode(GIT_PATH_UTF8_ENCODING)


def _unquote_git_path_token(path_token: str) -> str:
    """Return *path_token* with surrounding git quotes and C-escapes removed.

    Args:
        path_token: A single path token from a ``diff --git`` header.

    Returns:
        The unquoted path text, still carrying any ``a/`` or ``b/`` prefix.
    """
    quote_delimiter = GIT_QUOTED_PATH_DELIMITER
    if not (
        path_token.startswith(quote_delimiter)
        and path_token.endswith(quote_delimiter)
        and len(path_token) > len(quote_delimiter)
    ):
        return path_token
    return _decode_git_c_style_escapes(path_token[1:-1])


def _read_next_git_path_token(header_rest: str, start_index: int) -> tuple[str, int]:
    """Read one quoted or bare path token from *header_rest* at *start_index*.

    Args:
        header_rest: The text after ``diff --git ``.
        start_index: Index of the first character of the next token.

    Returns:
        The raw token text and the index after it.
    """
    if start_index >= len(header_rest):
        return "", start_index
    quote_delimiter = GIT_QUOTED_PATH_DELIMITER
    if header_rest[start_index] != quote_delimiter:
        next_space_index = header_rest.find(" ", start_index)
        if next_space_index < 0:
            return header_rest[start_index:], len(header_rest)
        return header_rest[start_index:next_space_index], next_space_index
    escape_backslash = GIT_C_STYLE_ESCAPE_BACKSLASH
    cursor_index = start_index + 1
    while cursor_index < len(header_rest):
        current_character = header_rest[cursor_index]
        if current_character == escape_backslash:
            cursor_index += len(escape_backslash) + 1
            continue
        if current_character == quote_delimiter:
            return header_rest[start_index : cursor_index + 1], cursor_index + 1
        cursor_index += 1
    return header_rest[start_index:], len(header_rest)


def _strip_diff_path_side_prefix(path_with_side_prefix: str) -> str:
    """Strip the ``a/`` or ``b/`` side prefix from a ``diff --git`` path.

    Args:
        path_with_side_prefix: Path text that may start with ``a/`` or ``b/``.

    Returns:
        The repository-relative path without the side prefix.
    """
    if path_with_side_prefix.startswith(GIT_DIFF_SOURCE_PATH_PREFIX):
        return path_with_side_prefix[len(GIT_DIFF_SOURCE_PATH_PREFIX) :]
    if path_with_side_prefix.startswith(GIT_DIFF_DESTINATION_PATH_PREFIX):
        return path_with_side_prefix[len(GIT_DIFF_DESTINATION_PATH_PREFIX) :]
    return path_with_side_prefix


def _destination_path_from_quoted_diff_git_header(header_rest: str) -> str | None:
    """Return the destination path from a C-quoted ``diff --git`` header rest.

    ::

        ok:   "a/\\303\\251.py" "b/\\303\\251.py" -> é.py
        flag: missing second quoted token         -> None

    Args:
        header_rest: Text after ``diff --git ``, starting with a quote.

    Returns:
        The destination repository-relative POSIX path, or None when either
        quoted token is missing.
    """
    first_token, after_first_index = _read_next_git_path_token(header_rest, 0)
    if not first_token:
        return None
    second_start_index = after_first_index
    while second_start_index < len(header_rest) and header_rest[second_start_index] == " ":
        second_start_index += 1
    second_token, _after_second_index = _read_next_git_path_token(
        header_rest, second_start_index
    )
    if not second_token:
        return None
    destination_with_prefix = _unquote_git_path_token(second_token)
    return _strip_diff_path_side_prefix(destination_with_prefix).replace("\\", "/")


def _destination_path_from_unquoted_no_rename_header(header_rest: str) -> str | None:
    """Return path X from an unquoted ``a/X b/X`` header (``--no-renames`` form).

    ::

        ok:   a/pkg/a.py b/pkg/a.py -> pkg/a.py
        ok:   a/z b.py b/z b.py     -> z b.py
        flag: a/old.py b/new.py     -> None (source and destination differ)

    Git leaves ASCII-space paths unquoted, so tokenizing on the first space
    mis-reads ``a/z b.py b/z b.py`` as destination ``b.py``. Under
    ``--no-renames`` both sides carry the same path X; the unique split where
    the text after ``a/`` is ``X b/X`` recovers X even when X holds spaces.

    Args:
        header_rest: Text after ``diff --git ``, unquoted.

    Returns:
        The repository-relative POSIX path, or None when the rest is not a
        symmetric ``a/X b/X`` pair.
    """
    source_prefix = GIT_DIFF_SOURCE_PATH_PREFIX
    destination_separator = f" {GIT_DIFF_DESTINATION_PATH_PREFIX}"
    if not header_rest.startswith(source_prefix):
        return None
    body_after_source_prefix = header_rest[len(source_prefix) :]
    search_start_index = 0
    while True:
        separator_index = body_after_source_prefix.find(
            destination_separator, search_start_index
        )
        if separator_index < 0:
            return None
        candidate_path = body_after_source_prefix[:separator_index]
        remainder_path = body_after_source_prefix[
            separator_index + len(destination_separator) :
        ]
        if candidate_path and remainder_path == candidate_path:
            return candidate_path.replace("\\", "/")
        search_start_index = separator_index + 1


def _destination_path_from_diff_git_header(header_line: str) -> str | None:
    """Return the destination relative path from a ``diff --git`` header line.

    ::

        ok:   diff --git a/pkg/a.py b/pkg/a.py           -> pkg/a.py
        ok:   diff --git a/z b.py b/z b.py               -> z b.py
        ok:   diff --git "a/\\303\\251.py" "b/\\303\\251.py" -> é.py
        flag: not a diff --git header                    -> None

    Args:
        header_line: One line that may start with ``diff --git ``.

    Returns:
        The destination repository-relative POSIX path, or None when the line
        is not a parseable ``diff --git`` header.
    """
    if not header_line.startswith(DIFF_GIT_HEADER_PREFIX):
        return None
    header_rest = header_line[len(DIFF_GIT_HEADER_PREFIX) :]
    if not header_rest:
        return None
    if header_rest.startswith(GIT_QUOTED_PATH_DELIMITER):
        return _destination_path_from_quoted_diff_git_header(header_rest)
    return _destination_path_from_unquoted_no_rename_header(header_rest)


def parse_combined_diff_added_line_map(
    combined_diff_text: str,
) -> dict[str, set[int]]:
    """Split a multi-file unified diff into per-path added-line sets.

    ::

        input:  two ``diff --git`` stanzas, first adds line 2, second adds 1..2
        output: {"first.py": {2}, "second.py": {1, 2}}
        binary stanza and empty new file both map to an empty set

    Args:
        combined_diff_text: Full stdout of one ``git diff --unified=0`` call.

    Returns:
        Mapping from repository-relative POSIX path to added line numbers.
    """
    added_by_relative_path: dict[str, set[int]] = {}
    current_relative_path: str | None = None
    current_hunk_lines: list[str] = []
    for each_line in combined_diff_text.splitlines(keepends=True):
        maybe_destination_path = _destination_path_from_diff_git_header(
            each_line.rstrip("\r\n")
        )
        if maybe_destination_path is not None:
            if current_relative_path is not None:
                added_by_relative_path[current_relative_path] = parse_added_line_numbers(
                    "".join(current_hunk_lines)
                )
            current_relative_path = maybe_destination_path
            current_hunk_lines = [each_line]
            continue
        if current_relative_path is not None:
            current_hunk_lines.append(each_line)
    if current_relative_path is not None:
        added_by_relative_path[current_relative_path] = parse_added_line_numbers(
            "".join(current_hunk_lines)
        )
    return added_by_relative_path


def combined_added_line_map_since(
    repository_root: Path, merge_base: str
) -> dict[str, set[int]]:
    """Return the merge-base..HEAD added-line map from one combined diff.

    Runs ``git diff --unified=0 --no-renames <merge_base>..HEAD`` once and
    splits the stdout by ``diff --git`` headers. ``--no-renames`` keeps the
    map aligned with per-file pathspec diffs when ``diff.renames`` is on.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to diff.

    Returns:
        Mapping from repository-relative POSIX path to added line numbers.

    Raises:
        SystemExit: When the combined diff command returns non-zero.
    """
    all_git_arguments = [
        *ALL_GIT_DIFF_UNIFIED_ZERO_NO_RENAMES_COMMAND_PREFIX,
        f"{merge_base}..HEAD",
    ]
    combined_diff_text = _git_text_or_exit(
        repository_root,
        all_git_arguments,
        "code_rules_gate: git diff --unified=0 --no-renames failed",
    )
    return parse_combined_diff_added_line_map(combined_diff_text)


def combined_added_line_map_staged(
    repository_root: Path,
    all_relative_posix_paths: list[str] | None = None,
) -> dict[str, set[int]]:
    """Return the staged added-line map from one combined cached diff.

    Runs ``git diff --cached --unified=0 --no-renames`` once. When
    *all_relative_posix_paths* is provided, those paths are pathspec-filtered
    so non-code files are never diffed.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        all_relative_posix_paths: Optional pathspec list; empty means no files.

    Returns:
        Mapping from repository-relative POSIX path to staged-added line numbers.

    Raises:
        SystemExit: When the combined cached diff command returns non-zero.
    """
    if all_relative_posix_paths is not None and not all_relative_posix_paths:
        return {}
    all_git_arguments = list(ALL_GIT_DIFF_CACHED_UNIFIED_ZERO_NO_RENAMES_COMMAND)
    if all_relative_posix_paths is not None:
        all_git_arguments.append(GIT_DIFF_PATH_ARGUMENT_SEPARATOR)
        all_git_arguments.extend(all_relative_posix_paths)
    combined_diff_text = _git_text_or_exit(
        repository_root,
        all_git_arguments,
        "code_rules_gate: git diff --cached --unified=0 --no-renames failed",
    )
    return parse_combined_diff_added_line_map(combined_diff_text)


def is_file_new_at_base(repository_root: Path, merge_base: str, relative_path_posix: str) -> bool:
    """Check whether *relative_path_posix* did not exist at *merge_base*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to check existence.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        True when the blob is absent at the merge base (added on the HEAD side).
    """
    completed = _run_git_text_capture(
        repository_root,
        ["git", "cat-file", "-e", f"{merge_base}:{relative_path_posix}"],
    )
    return completed.returncode != 0


def added_lines_for_file(
    repository_root: Path,
    merge_base: str,
    relative_path_posix: str,
    all_combined_added_lines: dict[str, set[int]] | None = None,
) -> set[int]:
    """Return added line numbers for *relative_path_posix* since *merge_base*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to diff.
        relative_path_posix: Repository-relative POSIX path to inspect.
        all_combined_added_lines: Optional precomputed map from one combined
            ``git diff --unified=0 --no-renames``; when the path is present the
            map value is returned and no per-file diff runs.

    Returns:
        The line numbers added on the HEAD side of the diff.

    Raises:
        SystemExit: When the diff command returns non-zero.
    """
    if (
        all_combined_added_lines is not None
        and relative_path_posix in all_combined_added_lines
    ):
        return all_combined_added_lines[relative_path_posix]
    diff_text = _git_text_or_exit(
        repository_root,
        ["git", "diff", "--unified=0", f"{merge_base}..HEAD", "--", relative_path_posix],
        f"code_rules_gate: git diff --unified=0 failed for {relative_path_posix}",
    )
    if not diff_text.strip():
        return set()
    return parse_added_line_numbers(diff_text)


def whole_file_line_set(file_path: Path) -> set[int]:
    """Return the set of line numbers covering an entire file.

    Args:
        file_path: Path to the file whose line span is summarized.

    Returns:
        Every line number in *file_path*, or an empty set when it is unreadable
        or empty.
    """
    try:
        total_lines = len(file_path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError) as read_error:
        sys.stderr.write(f"code_rules_gate: skipping unreadable file {file_path}: {read_error}\n")
        return set()
    if total_lines <= 0:
        return set()
    return set(range(1, total_lines + 1))


def _rename_pairs_from_tokens(all_tokens: list[str]) -> dict[str, str]:
    """Walk null-separated name-status tokens into destination-to-source pairs.

    Args:
        all_tokens: The decoded name-status tokens, in stream order.

    Returns:
        A mapping from rename-destination path to rename-source path.
    """
    rename_source_by_destination: dict[str, str] = {}
    next_token_index = 0
    while next_token_index < len(all_tokens):
        status_code = all_tokens[next_token_index]
        if not status_code.startswith(GIT_NAME_STATUS_RENAMED_PREFIX):
            next_token_index += EXPECTED_NON_RENAME_COLUMN_COUNT
            continue
        if next_token_index + EXPECTED_RENAME_COLUMN_COUNT > len(all_tokens):
            break
        rename_slice = all_tokens[
            next_token_index + 1 : next_token_index + EXPECTED_RENAME_COLUMN_COUNT
        ]
        destination_path = rename_slice[1].replace("\\", "/")
        rename_source_by_destination[destination_path] = rename_slice[0].replace("\\", "/")
        next_token_index += EXPECTED_RENAME_COLUMN_COUNT
    return rename_source_by_destination


def renamed_file_source_map_since(repository_root: Path, merge_base: str) -> dict[str, str]:
    """Return a mapping from rename-destination path to rename-source path.

    ::

        ok: a path holding a tab byte round-trips through the -z stream unmangled

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to diff.

    Returns:
        A mapping from rename-destination POSIX path to rename-source path.

    Raises:
        SystemExit: When ``git diff --name-status`` returns non-zero.
    """
    raw_stdout = _git_bytes_or_exit(
        repository_root,
        ["git", "diff", "--name-status", "-M", "-z", f"{merge_base}..HEAD"],
        "code_rules_gate: git diff --name-status -M -z failed",
    )
    all_tokens = [
        each_token.decode("utf-8", errors="replace")
        for each_token in raw_stdout.split(b"\x00")
        if each_token
    ]
    return _rename_pairs_from_tokens(all_tokens)


def added_lines_for_renamed_file(
    repository_root: Path,
    merge_base: str,
    source_posix: str,
    destination_posix: str,
) -> set[int]:
    """Return added line numbers for a renamed file via blob comparison.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to compare blobs.
        source_posix: Rename-source POSIX path at the merge base.
        destination_posix: Rename-destination POSIX path at HEAD.

    Returns:
        The line numbers added on the HEAD side; empty on diff failure.
    """
    source_reference = f"{merge_base}:{source_posix}"
    destination_reference = f"HEAD:{destination_posix}"
    completed = _run_git_text_capture(
        repository_root,
        ["git", "diff", "--unified=0", source_reference, destination_reference],
    )
    if completed.returncode != 0:
        sys.stderr.write(f"code_rules_gate: rename diff failed: {completed.stderr.strip()}\n")
        return set()
    if not completed.stdout.strip():
        return set()
    return parse_added_line_numbers(completed.stdout)


def _resolved_under_root(each_path: Path, resolved_root: Path) -> Path | None:
    """Return *each_path* resolved when it sits under *resolved_root*, else None."""
    try:
        resolved = each_path.resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved


def _added_lines_for_one_path(
    resolved_root: Path,
    merge_base: str,
    all_rename_sources: dict[str, str],
    resolved: Path,
    all_combined_added_lines: dict[str, set[int]],
) -> set[int]:
    """Resolve added lines for one path, honoring renames and new files.

    Args:
        resolved_root: The resolved repository root.
        merge_base: The merge-base SHA against which to diff.
        all_rename_sources: Destination-to-source rename map for the range.
        resolved: The resolved absolute path to inspect.
        all_combined_added_lines: Precomputed combined-diff map for the range.

    Returns:
        The added line numbers for the path.
    """
    relative_posix = str(resolved.relative_to(resolved_root)).replace("\\", "/")
    if relative_posix in all_rename_sources:
        return added_lines_for_renamed_file(
            resolved_root, merge_base, all_rename_sources[relative_posix], relative_posix
        )
    added_numbers = added_lines_for_file(
        resolved_root,
        merge_base,
        relative_posix,
        all_combined_added_lines=all_combined_added_lines,
    )
    if (
        not added_numbers
        and resolved.is_file()
        and is_file_new_at_base(resolved_root, merge_base, relative_posix)
    ):
        return whole_file_line_set(resolved)
    return added_numbers


def added_lines_by_file(
    repository_root: Path,
    base_reference: str,
    all_file_paths: list[Path],
    resolved_merge_base: str | None = None,
) -> dict[Path, set[int]]:
    """Build a per-file map of added line numbers across the branch.

    Args:
        repository_root: Repository root for diff invocations.
        base_reference: The git reference to merge-base against.
        all_file_paths: File paths whose added lines are collected.
        resolved_merge_base: Pre-resolved merge-base SHA; when omitted, the
            merge base of HEAD and *base_reference* is resolved here.

    Returns:
        A mapping from resolved file path to its added line numbers, with
        renames resolved against the original source path.
    """
    merge_base = (
        resolved_merge_base
        if resolved_merge_base is not None
        else resolve_merge_base(repository_root, base_reference)
    )
    resolved_root = repository_root.resolve()
    all_rename_sources = renamed_file_source_map_since(resolved_root, merge_base)
    all_combined_added_lines = combined_added_line_map_since(resolved_root, merge_base)
    added_by_path: dict[Path, set[int]] = {}
    for each_path in all_file_paths:
        resolved = _resolved_under_root(each_path, resolved_root)
        if resolved is None:
            continue
        added_by_path[resolved] = _added_lines_for_one_path(
            resolved_root,
            merge_base,
            all_rename_sources,
            resolved,
            all_combined_added_lines,
        )
    return added_by_path
