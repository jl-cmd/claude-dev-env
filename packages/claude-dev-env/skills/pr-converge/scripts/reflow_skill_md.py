"""Reflow packages/claude-dev-env/skills/pr-converge/SKILL.md to 80 columns.

Merge soft line breaks outside fenced blocks (space join; URL path fragments
joined without a space only inside unfinished markdown link targets), then
wrap with textwrap. Preserves fenced blocks verbatim.

Run: python3 packages/claude-dev-env/skills/pr-converge/scripts/reflow_skill_md.py
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from re import Match

script_directory = str(Path(__file__).resolve().parent)
while script_directory in sys.path:
    sys.path.remove(script_directory)
if script_directory not in sys.path:
    sys.path.insert(0, script_directory)

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    BASH_CONTINUATION_INDENT,
    BASH_FENCE_LANGUAGE,
    BASH_LINE_CONTINUATION_MARKER_WIDTH,
    BASH_LINE_CONTINUATION_SUFFIX,
    BASH_MINIMUM_SEGMENT_WIDTH,
    BULLET_MARKDOWN_LIST_PATTERN,
    CODE_FENCE_MARKER_LENGTH,
    EXAMPLE_CLOSE_TAG,
    EXAMPLE_OPEN_TAG,
    LONG_ROW_PREVIEW_LIMIT,
    MARKDOWN_CODE_FENCE_MARKER,
    MARKDOWN_HEADING_PATTERN,
    MARKDOWN_REFERENCE_DEFINITION_PATTERN,
    ORDERED_MARKDOWN_LIST_PATTERN,
    PR_CONVERGE_SKILL_PATH,
    REFLOW_FRONT_MATTER_ERROR,
    SKILL_REFLOW_MAXIMUM_WIDTH,
    UNFINISHED_MARKDOWN_LINK_TARGET_PATTERN,
    YAML_DESCRIPTION_PREFIX,
    YAML_FRONT_MATTER_DELIMITER,
)


def wrap_paragraph_plain(text: str) -> list[str]:
    """Wrap plain markdown paragraph text."""
    collapsed = " ".join(text.split())
    if not collapsed:
        return []
    return textwrap.fill(
        collapsed,
        width=SKILL_REFLOW_MAXIMUM_WIDTH,
        break_long_words=False,
        break_on_hyphens=False,
    ).splitlines()


def wrap_list_item(leading_whitespace: str, marker: str, body: str) -> list[str]:
    """Wrap one markdown list item with hanging indentation."""
    collapsed = " ".join(body.split())
    if not collapsed:
        return [leading_whitespace + marker.rstrip()]
    prefix = leading_whitespace + marker
    subsequent = leading_whitespace + (" " * len(marker))
    return textwrap.fill(
        collapsed,
        width=SKILL_REFLOW_MAXIMUM_WIDTH,
        initial_indent=prefix,
        subsequent_indent=subsequent,
        break_long_words=False,
        break_on_hyphens=False,
    ).splitlines()


def reflow_yaml_description_block(
    all_lines: list[str], body_start: int
) -> tuple[list[str], int]:
    """Reflow the front matter description block and return the next index."""
    all_body_parts: list[str] = []
    index = body_start
    while index < len(all_lines):
        line = all_lines[index]
        if line.strip() == YAML_FRONT_MATTER_DELIMITER:
            index += 1
            break
        stripped = line.lstrip()
        if stripped:
            all_body_parts.append(stripped)
        index += 1
    merged = " ".join(all_body_parts)
    wrapped = textwrap.fill(
        merged,
        width=SKILL_REFLOW_MAXIMUM_WIDTH,
        initial_indent="  ",
        subsequent_indent="  ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped.splitlines(), index


def is_table_line(line: str) -> bool:
    """Return whether the markdown line is a table row."""
    return line.lstrip().startswith("|")


def is_new_logical_line(stripped: str) -> bool:
    """Return whether stripped text starts a separate markdown block."""
    if not stripped:
        return False
    if stripped.startswith(MARKDOWN_CODE_FENCE_MARKER):
        return True
    if is_table_line(stripped):
        return True
    if stripped == YAML_FRONT_MATTER_DELIMITER:
        return True
    if MARKDOWN_HEADING_PATTERN.match(stripped):
        return True
    if MARKDOWN_REFERENCE_DEFINITION_PATTERN.match(stripped):
        return True
    if stripped.startswith(EXAMPLE_OPEN_TAG) or stripped.startswith(EXAMPLE_CLOSE_TAG):
        return True
    if ORDERED_MARKDOWN_LIST_PATTERN.match(stripped) or BULLET_MARKDOWN_LIST_PATTERN.match(
        stripped
    ):
        return True
    return False


def merge_without_space(buffer: str, continuation: str) -> bool:
    """Join without space only for split markdown link URL paths."""
    base = buffer.rstrip()
    stripped = continuation.lstrip()
    if not base or not stripped:
        return False
    if stripped.startswith("/") and UNFINISHED_MARKDOWN_LINK_TARGET_PATTERN.search(base):
        return True
    return False


def merge_soft_breaks(all_lines: list[str]) -> list[str]:
    """Merge soft markdown line breaks outside fenced blocks."""
    all_merged_lines: list[str] = []
    index = 0
    is_in_fence = False
    while index < len(all_lines):
        raw = all_lines[index]
        line = raw.rstrip("\n")
        if line.lstrip().startswith(MARKDOWN_CODE_FENCE_MARKER):
            is_in_fence = not is_in_fence
            all_merged_lines.append(line)
            index += 1
            continue
        if is_in_fence:
            all_merged_lines.append(line)
            index += 1
            continue
        if line.strip() == "":
            all_merged_lines.append(line)
            index += 1
            continue
        buffer_line, index = merge_continuation_lines(all_lines, line, index + 1)
        all_merged_lines.append(buffer_line)
    return all_merged_lines


def merge_continuation_lines(
    all_lines: list[str], buffer_line: str, start_index: int
) -> tuple[str, int]:
    """Merge continuation lines until a markdown boundary appears."""
    index = start_index
    while index < len(all_lines):
        next_raw = all_lines[index].rstrip("\n")
        stripped_next = next_raw.lstrip()
        if should_stop_soft_merge(next_raw, stripped_next):
            break
        buffer_line = combine_continuation_line(buffer_line, stripped_next)
        index += 1
    return buffer_line, index


def should_stop_soft_merge(next_raw: str, stripped_next: str) -> bool:
    """Return whether a candidate continuation starts a new markdown block."""
    if next_raw.strip() == "":
        return True
    if stripped_next.startswith(MARKDOWN_CODE_FENCE_MARKER):
        return True
    return is_new_logical_line(stripped_next)


def combine_continuation_line(buffer_line: str, stripped_next: str) -> str:
    """Join a continuation with or without a separating space."""
    if merge_without_space(buffer_line, stripped_next):
        return buffer_line.rstrip() + stripped_next
    return f"{buffer_line.rstrip()} {stripped_next}"


def reflow_merged_line(line: str) -> list[str]:
    """Reflow a merged markdown line according to its block type."""
    stripped = line.strip()
    structural_lines = reflow_structural_line(line, stripped)
    if structural_lines is not None:
        return structural_lines
    ordered = ORDERED_MARKDOWN_LIST_PATTERN.match(line)
    if ordered:
        return wrap_match_list_item(ordered)
    bullet = BULLET_MARKDOWN_LIST_PATTERN.match(line)
    if bullet:
        return wrap_match_list_item(bullet)
    return wrap_paragraph_plain(stripped)


def reflow_structural_line(line: str, stripped: str) -> list[str] | None:
    """Return structural markdown lines that should not use paragraph wrapping."""
    if stripped == "":
        return [""]
    if stripped.startswith(MARKDOWN_CODE_FENCE_MARKER):
        return [line]
    if MARKDOWN_HEADING_PATTERN.match(stripped):
        return reflow_heading_line(stripped)
    if (
        stripped == YAML_FRONT_MATTER_DELIMITER
        or is_table_line(stripped)
        or MARKDOWN_REFERENCE_DEFINITION_PATTERN.match(stripped)
    ):
        return [stripped]
    if stripped.startswith(EXAMPLE_CLOSE_TAG):
        return [stripped]
    if stripped.startswith(EXAMPLE_OPEN_TAG):
        return reflow_example_line(stripped)
    return None


def wrap_match_list_item(match_result: Match[str]) -> list[str]:
    """Wrap a regex-matched markdown list item."""
    return wrap_list_item(
        match_result.group("leading_whitespace"),
        match_result.group("marker"),
        match_result.group("body"),
    )


def reflow_heading_line(stripped: str) -> list[str]:
    """Reflow one markdown heading line."""
    if len(stripped) <= SKILL_REFLOW_MAXIMUM_WIDTH:
        return [stripped]
    title = stripped.lstrip("#").strip()
    level = len(stripped) - len(stripped.lstrip("#"))
    prefix = "#" * level + " "
    return textwrap.fill(
        title,
        width=SKILL_REFLOW_MAXIMUM_WIDTH,
        initial_indent=prefix,
        subsequent_indent=prefix,
        break_long_words=False,
        break_on_hyphens=False,
    ).splitlines()


def reflow_example_line(stripped: str) -> list[str]:
    """Reflow one example tag line."""
    inner = stripped[len(EXAMPLE_OPEN_TAG) :].strip()
    if not inner:
        return [EXAMPLE_OPEN_TAG]
    tag = f"{EXAMPLE_OPEN_TAG} "
    subsequent = " " * len(tag)
    return textwrap.fill(
        " ".join(inner.split()),
        width=SKILL_REFLOW_MAXIMUM_WIDTH,
        initial_indent=tag,
        subsequent_indent=subsequent,
        break_long_words=False,
        break_on_hyphens=False,
    ).splitlines()


def reflow_markdown_body(all_lines: list[str]) -> list[str]:
    """Reflow markdown body lines after front matter."""
    merged = merge_soft_breaks(all_lines)
    all_reflowed_lines: list[str] = []
    for each_line in merged:
        if each_line.strip() == "":
            all_reflowed_lines.append("")
            continue
        all_reflowed_lines.extend(reflow_merged_line(each_line))
    return all_reflowed_lines


def wrap_long_bash_fence_lines(all_lines: list[str]) -> list[str]:
    """Hard-wrap only long ```bash fence body lines."""
    all_wrapped_lines: list[str] = []
    is_in_bash_fence = False
    for each_line in all_lines:
        stripped = each_line.lstrip()
        if stripped.startswith(MARKDOWN_CODE_FENCE_MARKER):
            is_in_bash_fence = is_next_line_in_bash_fence(stripped, is_in_bash_fence)
            all_wrapped_lines.append(each_line)
            continue
        all_wrapped_lines.extend(wrap_bash_line_if_needed(each_line, is_in_bash_fence))
    return all_wrapped_lines


def is_next_line_in_bash_fence(stripped: str, is_in_bash_fence: bool) -> bool:
    """Return the next bash-fence state after a fence marker."""
    if is_in_bash_fence:
        return False
    language = stripped[CODE_FENCE_MARKER_LENGTH:].strip().lower()
    return language == BASH_FENCE_LANGUAGE


def wrap_bash_line_if_needed(each_line: str, is_in_bash_fence: bool) -> list[str]:
    """Return a wrapped bash line when it exceeds the configured width."""
    if not is_in_bash_fence:
        return [each_line]
    if len(each_line) <= SKILL_REFLOW_MAXIMUM_WIDTH:
        return [each_line]
    return wrap_long_bash_line(each_line)


def wrap_long_bash_line(each_line: str) -> list[str]:
    """Wrap one long bash fence line with continuation markers."""
    indent_length = len(each_line) - len(each_line.lstrip())
    indent = each_line[:indent_length]
    minimum_content_width = (
        BASH_LINE_CONTINUATION_MARKER_WIDTH + BASH_MINIMUM_SEGMENT_WIDTH
    )
    if len(indent) + minimum_content_width >= SKILL_REFLOW_MAXIMUM_WIDTH:
        return [each_line]
    rest = each_line.lstrip()
    all_wrapped_segments: list[str] = []
    while len(rest) > bash_tail_width(indent, bool(all_wrapped_segments)):
        rest = append_bash_continuation_segment(rest, indent, all_wrapped_segments)
    if rest:
        continuation_indent = BASH_CONTINUATION_INDENT if all_wrapped_segments else ""
        all_wrapped_segments.append(indent + continuation_indent + rest)
    return all_wrapped_segments


def bash_tail_width(indent: str, has_wrapped_segments: bool) -> int:
    """Return content width left for the final bash segment."""
    continuation_indent_length = (
        len(BASH_CONTINUATION_INDENT) if has_wrapped_segments else 0
    )
    return SKILL_REFLOW_MAXIMUM_WIDTH - len(indent) - continuation_indent_length


def append_bash_continuation_segment(
    rest: str, indent: str, all_wrapped_segments: list[str]
) -> str:
    """Append one continuation segment and return remaining text."""
    available_width = (
        SKILL_REFLOW_MAXIMUM_WIDTH - len(indent) - BASH_LINE_CONTINUATION_MARKER_WIDTH
    )
    window = rest[:available_width]
    break_at = window.rfind(" ")
    if break_at <= 0:
        break_at = available_width
    piece = rest[:break_at].rstrip()
    all_wrapped_segments.append(indent + piece + BASH_LINE_CONTINUATION_SUFFIX)
    return rest[break_at:].lstrip()


def split_front_matter(all_skill_lines: list[str]) -> tuple[list[str], int]:
    """Return reflowed front matter and the body start index."""
    all_front_matter_lines = [YAML_FRONT_MATTER_DELIMITER]
    index = 1
    while index < len(all_skill_lines):
        line = all_skill_lines[index]
        if line.startswith(YAML_DESCRIPTION_PREFIX):
            all_front_matter_lines.append(line)
            index += 1
            all_description_lines, index = reflow_yaml_description_block(
                all_skill_lines, index
            )
            all_front_matter_lines.extend(all_description_lines)
            all_front_matter_lines.append(YAML_FRONT_MATTER_DELIMITER)
            break
        all_front_matter_lines.append(line)
        index += 1
    return all_front_matter_lines, index


def reflow_skill_markdown(skill_markdown: str) -> str:
    """Return reflowed pr-converge skill markdown."""
    all_skill_lines = skill_markdown.splitlines()
    if not all_skill_lines or all_skill_lines[0].strip() != YAML_FRONT_MATTER_DELIMITER:
        raise SystemExit(REFLOW_FRONT_MATTER_ERROR)
    all_front_matter_lines, index = split_front_matter(all_skill_lines)
    all_body_lines = reflow_markdown_body(all_skill_lines[index:])
    all_wrapped_body_lines = wrap_long_bash_fence_lines(all_body_lines)
    return "\n".join(all_front_matter_lines + all_wrapped_body_lines) + "\n"


def write_reflow_summary(reflowed_skill_markdown: str) -> None:
    """Write the reflow summary to stdout."""
    all_lines = reflowed_skill_markdown.splitlines()
    all_long_rows = [
        (i, len(each_line_text))
        for i, each_line_text in enumerate(all_lines, 1)
        if len(each_line_text) > SKILL_REFLOW_MAXIMUM_WIDTH
    ]
    sys.stdout.write(f"SKILL.md reflowed; lines: {len(all_lines)}\n")
    sys.stdout.write(
        "lines longer than %d: %d\n"
        % (SKILL_REFLOW_MAXIMUM_WIDTH, len(all_long_rows))
    )
    if all_long_rows[:LONG_ROW_PREVIEW_LIMIT]:
        sys.stdout.write(
            f"first long: {all_long_rows[:LONG_ROW_PREVIEW_LIMIT]}\n"
        )


def main() -> None:
    """Reflow the pr-converge SKILL.md file in place."""
    skill_path = PR_CONVERGE_SKILL_PATH
    reflowed_skill_markdown = reflow_skill_markdown(
        skill_path.read_text(encoding="utf-8")
    )
    skill_path.write_text(reflowed_skill_markdown, encoding="utf-8", newline="\n")
    write_reflow_summary(reflowed_skill_markdown)


if __name__ == "__main__":
    main()
