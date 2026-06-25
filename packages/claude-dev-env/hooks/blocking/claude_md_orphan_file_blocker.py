#!/usr/bin/env python3
"""PreToolUse hook: blocks a per-directory CLAUDE.md that names a file absent from its subtree.

A per-directory ``CLAUDE.md`` documents the files reachable from its own
directory in a markdown table whose first column names each file in backticks,
and shows run commands inside fenced code blocks that invoke those files. When a
first-column cell, or an interpreter invocation inside a fenced run command
(``python script.py``), names a bare filename that exists nowhere under the scan
root (the CLAUDE.md directory's parent, which covers the directory, its
subdirectories, and its siblings), the doc points a reader at a file that is not
there. This hook fires on Write, Edit, and MultiEdit targeting a file named
``CLAUDE.md`` and blocks the write when any such cell or run command names a file
absent from the scan root. A table block whose own region declares an explicit
relative-path source (a ``../`` token) documents files outside the subtree, so
that block's rows are left alone — the exemption is scoped to the block, not the
whole file.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.claude_md_orphan_file_blocker_constants import (  # noqa: E402
    ALL_NOISE_DIRECTORY_NAMES,
    ALL_REFERENCED_FILE_EXTENSIONS,
    ALL_RUN_COMMAND_SCRIPT_EXTENSIONS,
    CLAUDE_MD_FILENAME,
    CODE_FENCE_PATTERN,
    FIRST_COLUMN_BACKTICK_PATTERN,
    MAX_ORPHAN_FILE_ISSUES,
    MAX_SUBTREE_FILES_SCANNED,
    ORPHAN_FILE_ADDITIONAL_CONTEXT,
    ORPHAN_FILE_MESSAGE_TEMPLATE,
    ORPHAN_FILE_SYSTEM_MESSAGE,
    REGION_BOUNDARY_PATTERN,
    RELATIVE_PATH_SOURCE_PATTERN,
    RUN_COMMAND_SCRIPT_PATTERN,
    SEPARATOR_CELL_PATTERN,
    TABLE_ROW_PATTERN,
)
from hooks_constants.multi_edit_reconstruction import (  # noqa: E402
    apply_edits,
    edits_for_tool,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def is_claude_md_file(file_path: str) -> bool:
    """Return whether *file_path* names a per-directory ``CLAUDE.md`` file.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path's basename is exactly ``CLAUDE.md``.
    """
    return os.path.basename(file_path) == CLAUDE_MD_FILENAME


def _first_table_cell(table_line: str) -> str:
    """Return the trimmed text of the first column cell in a markdown table row.

    Args:
        table_line: A single line that begins with a pipe character.

    Returns:
        The text between the leading pipe and the next pipe, stripped of
        surrounding whitespace; an empty string when no cell is present.
    """
    after_leading_pipe = table_line.strip().lstrip("|")
    first_cell, _, _ = after_leading_pipe.partition("|")
    return first_cell.strip()


def _referenced_filename_in_cell(cell_text: str) -> str | None:
    """Return the bare filename a table cell references, when it has one.

    A cell references a bare filename only when its first backticked token has no
    path separator, is not a slash-command, and carries a known file extension.
    Subdirectory cells (trailing slash) and paths fall outside this scope and
    yield None.

    Args:
        cell_text: The trimmed text of a first-column table cell.

    Returns:
        The bare filename to verify in the subtree, or None when the cell names
        no bare file.
    """
    backtick_match = FIRST_COLUMN_BACKTICK_PATTERN.search(cell_text)
    if backtick_match is None:
        return None
    inner_text = backtick_match.group(1).strip()
    if not inner_text:
        return None
    if inner_text.startswith("/"):
        return None
    if "/" in inner_text or "\\" in inner_text:
        return None
    _, extension = os.path.splitext(inner_text)
    if extension.lower() not in ALL_REFERENCED_FILE_EXTENSIONS:
        return None
    return inner_text


def _filename_in_table_row(table_line: str) -> str | None:
    """Return the bare filename a markdown table row references, when it has one.

    Args:
        table_line: A single line that begins with a pipe character.

    Returns:
        The bare filename in the row's first column, or None when the row is a
        header-separator row or names no bare file.
    """
    first_cell = _first_table_cell(table_line)
    if not first_cell or SEPARATOR_CELL_PATTERN.match(first_cell):
        return None
    return _referenced_filename_in_cell(first_cell)


def _declares_relative_path_source(text: str) -> bool:
    """Return whether *text* declares an explicit relative-path file source.

    A ``../`` token signals that a table documents files in a sibling tree,
    referenced by path rather than living in the CLAUDE.md's own subtree. The
    block that carries such a token is out of scope, since its files legitimately
    sit outside the subtree.

    Args:
        text: A table block together with the prose that introduces it.

    Returns:
        True when *text* contains a ``../`` relative-path token.
    """
    return RELATIVE_PATH_SOURCE_PATTERN.search(text) is not None


def find_referenced_filenames(content: str) -> list[str]:
    """Return each bare filename a CLAUDE.md table references, in order.

    Walks the content line by line, grouping it into table blocks. A table block
    is a maximal run of consecutive markdown table rows; the prose region since
    the most recent heading introduces it, so prose under one section never
    introduces a table under a later section. A line inside a fenced code block
    (between a ``` or ~~~
    fence pair) is example or sample text, not a live table, so it contributes
    nothing and never ends a block. A block whose introducing region or own rows
    declare an explicit relative-path source (a ``../`` token) documents files in
    a sibling tree, so its rows are skipped — the exemption is scoped to that
    region and block, not the whole file. Every remaining block contributes the
    bare filename each first-column cell names.

    Args:
        content: The CLAUDE.md content being written.

    Returns:
        Each referenced filename from a non-exempt table block, in the order it
        appears; duplicates preserved.
    """
    referenced_filenames: list[str] = []
    pending_region: list[str] = []
    current_block: list[str] = []
    is_inside_code_fence = False
    for each_line in content.splitlines():
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            continue
        if is_inside_code_fence:
            continue
        if TABLE_ROW_PATTERN.match(each_line) is not None:
            current_block.append(each_line)
            continue
        if current_block:
            referenced_filenames.extend(_block_filenames(pending_region, current_block))
            current_block = []
            pending_region = []
        if REGION_BOUNDARY_PATTERN.match(each_line) is not None:
            pending_region = []
        pending_region.append(each_line)
    referenced_filenames.extend(_block_filenames(pending_region, current_block))
    return referenced_filenames


def _block_filenames(all_region_lines: list[str], all_block_lines: list[str]) -> list[str]:
    """Return the bare filenames a table block contributes, honoring its exemption.

    Args:
        all_region_lines: The prose lines accumulated before this block.
        all_block_lines: The consecutive table rows that form the block.

    Returns:
        Each bare filename the block's first-column cells name, or an empty list
        when the block (with its introducing region) declares a ``../`` source.
    """
    if not all_block_lines:
        return []
    block_region = "\n".join(all_region_lines + all_block_lines)
    if _declares_relative_path_source(block_region):
        return []
    block_filenames: list[str] = []
    for each_line in all_block_lines:
        each_filename = _filename_in_table_row(each_line)
        if each_filename is not None:
            block_filenames.append(each_filename)
    return block_filenames


def _run_command_filename_in_line(fenced_line: str) -> str | None:
    """Return the script basename an interpreter invocation on this line names.

    A fenced run-command line such as ``python tools/verify.py --flag`` invokes a
    script file; this returns that script's bare basename. A path-qualified script
    keeps only its final segment, so ``node tools/build_bundle.mjs`` yields
    ``build_bundle.mjs`` — the basename the directory file would match. A script
    named by an explicit relative-path source (a ``../`` token, as in
    ``python ../shared/preflight.py``) lives outside the subtree by design, so it
    is exempt and yields None, mirroring the table-cell ``../`` exemption. A line
    with no interpreter invocation, or whose named script carries no recognized
    extension, yields None.

    Args:
        fenced_line: A single line drawn from inside a fenced code block.

    Returns:
        The bare script basename the invocation names, or None when the line names
        no script or names one by an explicit relative-path source.
    """
    invocation_match = RUN_COMMAND_SCRIPT_PATTERN.search(fenced_line)
    if invocation_match is None:
        return None
    script_token = invocation_match.group(1).strip()
    if _declares_relative_path_source(script_token):
        return None
    basename = os.path.basename(script_token.replace("\\", "/").rstrip("/"))
    if not basename:
        return None
    _, extension = os.path.splitext(basename)
    if extension.lower() not in ALL_RUN_COMMAND_SCRIPT_EXTENSIONS:
        return None
    return basename


def find_run_command_filenames(content: str) -> list[str]:
    """Return each script basename a fenced run command invokes, in order.

    Walks the content line by line, inspecting only lines inside a fenced code
    block (between a ``` or ~~~ fence pair). A fenced run-command line that invokes
    an interpreter on a script (``python script.py``, ``node bundle.mjs``,
    ``pwsh build.ps1``) contributes that script's bare basename. A line outside any
    fence is prose, not a live command, and contributes nothing — an inline
    ``python x.py`` in a sentence is documentation, not a runnable contract.

    Args:
        content: The CLAUDE.md content being written.

    Returns:
        Each script basename a fenced run command names, in the order it appears;
        duplicates preserved.
    """
    run_command_filenames: list[str] = []
    is_inside_code_fence = False
    for each_line in content.splitlines():
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            continue
        if not is_inside_code_fence:
            continue
        each_filename = _run_command_filename_in_line(each_line)
        if each_filename is not None:
            run_command_filenames.append(each_filename)
    return run_command_filenames


def _resolve_scan_root(claude_md_directory: Path) -> Path:
    """Return the directory whose subtree bounds the filename existence search.

    The search root is the CLAUDE.md directory's parent when that parent exists,
    so a table that documents files in a sibling directory or one level up still
    resolves them. When the directory has no distinct parent, the CLAUDE.md
    directory itself is the root.

    Args:
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        The directory to walk when collecting candidate filenames.
    """
    parent_directory = claude_md_directory.parent
    if parent_directory == claude_md_directory:
        return claude_md_directory
    return parent_directory


class _SubtreeScan:
    """The basenames a bounded subtree walk collected and whether it ran complete.

    Attributes:
        all_basenames: Each file basename the walk reached.
        was_scan_complete: True when the walk visited the whole subtree within the
            budget, so ``all_basenames`` is authoritative; False when the budget
            truncated the walk, so a basename's absence from the set is not proof
            of its absence on disk.
    """

    def __init__(self, all_basenames: set[str], was_scan_complete: bool) -> None:
        self.all_basenames = all_basenames
        self.was_scan_complete = was_scan_complete


def _is_under_noise_directory(scan_root: Path, candidate_path: Path) -> bool:
    """Return whether *candidate_path* lies inside a pruned noise directory.

    A noise directory (``.git``, ``__pycache__``, ``node_modules``, and the test
    and lint caches) holds volatile generated files that no CLAUDE.md table
    documents, so the walk skips them. This keeps generated files out of the
    basename set and keeps them from consuming the scan budget.

    Args:
        scan_root: The directory the walk descends from.
        candidate_path: A path the walk yielded under the scan root.

    Returns:
        True when any path segment below *scan_root* names a noise directory.
    """
    try:
        relative_segments = candidate_path.relative_to(scan_root).parts
    except ValueError:
        relative_segments = candidate_path.parts
    return any(each_segment in ALL_NOISE_DIRECTORY_NAMES for each_segment in relative_segments)


def _scan_subtree_basenames(scan_root: Path) -> _SubtreeScan:
    """Return the bounded basename scan of *scan_root*, skipping unreadable entries.

    Walks the subtree collecting each file's basename, stopping once the scan
    budget is reached. A path inside a noise directory is pruned, and a per-entry
    stat error skips that entry. The result records whether the walk completed
    within the budget, so the caller knows whether the set is authoritative.

    Args:
        scan_root: The directory whose subtree bounds the existence search.

    Returns:
        The collected basenames paired with the scan-completeness flag.
    """
    all_basenames: set[str] = set()
    scanned_count = 0
    for each_path in scan_root.rglob("*"):
        if _is_under_noise_directory(scan_root, each_path):
            continue
        try:
            if not each_path.is_file():
                continue
        except OSError:
            continue
        all_basenames.add(each_path.name)
        scanned_count += 1
        if scanned_count >= MAX_SUBTREE_FILES_SCANNED:
            return _SubtreeScan(all_basenames, was_scan_complete=False)
    return _SubtreeScan(all_basenames, was_scan_complete=True)


def _filename_exists_under(scan_root: Path, filename: str) -> bool:
    """Return whether a file with basename *filename* exists anywhere under root.

    A direct probe that resolves one filename deterministically even when the
    bounded subtree walk was truncated. A match inside a noise directory is pruned
    so the probe agrees with the bounded walk, and an unreadable entry mid-walk is
    skipped.

    Args:
        scan_root: The directory whose subtree bounds the existence search.
        filename: The bare basename to look for.

    Returns:
        True when at least one matching file is reachable under the scan root.
    """
    for each_match in scan_root.rglob(filename):
        if _is_under_noise_directory(scan_root, each_match):
            continue
        try:
            if each_match.is_file():
                return True
        except OSError:
            continue
    return False


def _present_referenced_filenames(
    all_referenced_filenames: list[str], scan_root: Path
) -> set[str]:
    """Return the referenced filenames that exist under the scan root.

    A complete bounded walk yields an authoritative basename set, so membership in
    it decides presence. When the budget truncated the walk, a name absent from
    the partial set is probed directly with ``rglob`` so a truncated slice never
    produces a false-missing verdict.

    Args:
        all_referenced_filenames: The bare filenames a CLAUDE.md table names.
        scan_root: The directory whose subtree bounds the existence search.

    Returns:
        The subset of *all_referenced_filenames* that resolve to an existing file.
    """
    subtree_scan = _scan_subtree_basenames(scan_root)
    present_filenames: set[str] = set()
    for each_filename in all_referenced_filenames:
        if each_filename in subtree_scan.all_basenames:
            present_filenames.add(each_filename)
            continue
        if subtree_scan.was_scan_complete:
            continue
        if _filename_exists_under(scan_root, each_filename):
            present_filenames.add(each_filename)
    return present_filenames


def find_missing_filenames(content: str, claude_md_directory: Path) -> list[str]:
    """Return the referenced filenames absent from the CLAUDE.md's scan root.

    A referenced filename comes from two sources: a bare filename a table cell
    names, and a script a fenced run command invokes (``python script.py``). It is
    missing when it exists nowhere under the scan root — the CLAUDE.md directory's
    parent (or the directory itself when it has no distinct parent), which covers
    the directory, its subdirectories, and its siblings. A table block that
    declares an explicit relative-path source (a ``../`` token in the block or the
    prose that introduces it) yields no findings for that block's rows, since those
    files legitimately live elsewhere; an unrelated block in the same file is still
    checked. When the content references no bare filename, no findings result and
    the subtree walk is skipped. A filesystem error that halts the whole subtree
    walk yields no findings (fail open), so an unreadable tree never blocks a write.

    Args:
        content: The CLAUDE.md content being written.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each referenced filename with no matching file under the scan root, in
        first-seen order with duplicates removed, capped at the issue budget.
    """
    referenced_filenames = find_referenced_filenames(content) + find_run_command_filenames(
        content
    )
    if not referenced_filenames:
        return []
    scan_root = _resolve_scan_root(claude_md_directory)
    try:
        present_filenames = _present_referenced_filenames(referenced_filenames, scan_root)
    except OSError:
        return []
    missing_filenames: list[str] = []
    already_reported: set[str] = set()
    for each_filename in referenced_filenames:
        if each_filename in already_reported:
            continue
        if each_filename in present_filenames:
            continue
        already_reported.add(each_filename)
        missing_filenames.append(each_filename)
        if len(missing_filenames) >= MAX_ORPHAN_FILE_ISSUES:
            break
    return missing_filenames


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the current on-disk content of *file_path*, or None when unreadable.

    Args:
        file_path: The path of the file the edit targets.

    Returns:
        The file's text, or None when the file is missing or cannot be decoded.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _edit_fragments(all_edits: list[dict]) -> list[str]:
    """Return each MultiEdit ``new_string`` fragment present as a non-empty string.

    Args:
        all_edits: The MultiEdit ``edits`` list.

    Returns:
        Every ``new_string`` value that is a non-empty string, in list order.
    """
    all_fragments: list[str] = []
    for each_edit in all_edits:
        if not isinstance(each_edit, dict):
            continue
        new_string = each_edit.get("new_string", "")
        if isinstance(new_string, str) and new_string:
            all_fragments.append(new_string)
    return all_fragments


class _OrphanScanPlan:
    """The contents to scan for orphans and the pre-existing orphans to exclude.

    Attributes:
        candidate_contents: Each content string whose table rows are scanned.
        baseline_missing_filenames: The orphan filenames the file already held
            before this edit; reporting excludes them so an unrelated edit over a
            pre-existing orphan on an untouched line is not blocked. Empty for a
            Write (the whole file is replaced) and for an edit whose existing file
            cannot be read.
    """

    def __init__(
        self, all_candidate_contents: list[str], all_baseline_missing_filenames: set[str]
    ) -> None:
        self.candidate_contents = all_candidate_contents
        self.baseline_missing_filenames = all_baseline_missing_filenames


def _build_orphan_scan_plan(
    tool_name: str, tool_input: dict, file_path: str, claude_md_directory: Path
) -> _OrphanScanPlan:
    """Return the contents to scan and the pre-existing orphans to exclude.

    For Write the candidate is the full new content with no baseline, so every
    orphan it names is introduced by the write. For Edit and MultiEdit the
    candidate is the existing file with the replacements applied, so a ``../``
    source line outside the edited rows still exempts that table block; the
    baseline is the orphan set the existing file already held, so a pre-existing
    orphan on an untouched line is excluded and only an orphan the edit introduces
    is reported. When the existing file cannot be read, the raw ``new_string``
    fragment(s) are scanned with no baseline, so an orphan the edit itself adds is
    still caught.

    Args:
        tool_name: The intercepted tool — ``Write``, ``Edit``, or ``MultiEdit``.
        tool_input: The tool's input payload.
        file_path: The destination path of the write or edit.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        The scan plan pairing candidate contents with the baseline orphan set.
    """
    if tool_name == "Write":
        content = tool_input.get("content", "")
        candidate_contents = [content] if isinstance(content, str) and content else []
        return _OrphanScanPlan(candidate_contents, set())
    all_edits = edits_for_tool(tool_name, tool_input)
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        return _OrphanScanPlan(_edit_fragments(all_edits), set())
    baseline_missing = set(find_missing_filenames(existing_content, claude_md_directory))
    return _OrphanScanPlan([apply_edits(existing_content, all_edits)], baseline_missing)


def _collect_missing_filenames(scan_plan: _OrphanScanPlan, claude_md_directory: Path) -> list[str]:
    """Return every orphan filename the scan plan introduces, excluding baselines.

    An orphan the file already held before the edit (a member of the plan's
    baseline set) is excluded, so an unrelated edit over a pre-existing orphan on
    an untouched line reports nothing.

    Args:
        scan_plan: The candidate contents to scan paired with the baseline orphan
            set to exclude.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each introduced orphan filename in first-seen order with duplicates
        removed, capped at the issue budget.
    """
    missing_filenames: list[str] = []
    already_reported: set[str] = set()
    for each_content in scan_plan.candidate_contents:
        for each_filename in find_missing_filenames(each_content, claude_md_directory):
            if each_filename in scan_plan.baseline_missing_filenames:
                continue
            if each_filename in already_reported:
                continue
            already_reported.add(each_filename)
            missing_filenames.append(each_filename)
            if len(missing_filenames) >= MAX_ORPHAN_FILE_ISSUES:
                return missing_filenames
    return missing_filenames


def _build_block_payload(all_missing_filenames: list[str], directory: str) -> dict:
    """Build the PreToolUse deny payload listing each missing filename.

    Args:
        all_missing_filenames: The referenced filenames absent from the subtree.
        directory: The directory that holds the target CLAUDE.md.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    formatted_missing = ", ".join(f"`{each_name}`" for each_name in all_missing_filenames)
    reason = ORPHAN_FILE_MESSAGE_TEMPLATE.format(directory=directory, missing=formatted_missing)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": ORPHAN_FILE_ADDITIONAL_CONTEXT,
        },
        "systemMessage": ORPHAN_FILE_SYSTEM_MESSAGE,
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
    """Read the PreToolUse payload from stdin and block an orphan-file CLAUDE.md."""
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_claude_md_file(file_path):
        sys.exit(0)

    claude_md_directory = Path(file_path).resolve().parent
    if not claude_md_directory.is_dir():
        sys.exit(0)

    scan_plan = _build_orphan_scan_plan(tool_name, tool_input, file_path, claude_md_directory)
    if not scan_plan.candidate_contents:
        sys.exit(0)

    missing_filenames = _collect_missing_filenames(scan_plan, claude_md_directory)
    if not missing_filenames:
        sys.exit(0)

    block_payload = _build_block_payload(missing_filenames, str(claude_md_directory))
    log_hook_block(
        calling_hook_name="claude_md_orphan_file_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
