"""Reflow packages/claude-dev-env/skills/pr-converge/SKILL.md to 80 columns.

Merge soft line breaks outside fenced blocks (space join; URL path fragments
joined without a space only inside unfinished markdown link targets), then
wrap with textwrap. Preserves fenced blocks verbatim.

Run: python3 packages/claude-dev-env/skills/pr-converge/scripts/reflow_skill_md.py
"""

from __future__ import annotations

import textwrap

from config.reflow_skill_md_constants import (
    BASH_CONTINUATION_MARKER_WIDTH,
    BULLET_LIST_ITEM_PATTERN as BULLET_RE,
    MARKDOWN_REFERENCE_DEFINITION_PATTERN as REF_DEF_RE,
    MAXIMUM_LINE_WIDTH as MAX_WIDTH,
    ORDERED_LIST_ITEM_PATTERN as ORDERED_RE,
    TARGET_SKILL_PATH as SKILL_PATH,
    UNFINISHED_MARKDOWN_LINK_TARGET_PATTERN as UNFINISHED_MD_LINK_TARGET,
)


def wrap_paragraph_plain(text: str) -> list[str]:
    collapsed = " ".join(text.split())
    if not collapsed:
        return []
    return textwrap.fill(
        collapsed,
        width=MAX_WIDTH,
        break_long_words=False,
        break_on_hyphens=False,
    ).splitlines()


def wrap_list_item(lead_ws: str, marker: str, body: str) -> list[str]:
    collapsed = " ".join(body.split())
    if not collapsed:
        return [lead_ws + marker.rstrip()]
    prefix = lead_ws + marker
    subsequent = lead_ws + (" " * len(marker))
    return textwrap.fill(
        collapsed,
        width=MAX_WIDTH,
        initial_indent=prefix,
        subsequent_indent=subsequent,
        break_long_words=False,
        break_on_hyphens=False,
    ).splitlines()


def reflow_yaml_description_block(
    all_lines: list[str],
    body_start: int,
) -> tuple[list[str], int]:
    body_parts: list[str] = []
    index = body_start
    while index < len(all_lines):
        line = all_lines[index]
        if line.strip() == "---":
            index += 1
            break
        stripped = line.lstrip()
        if stripped:
            body_parts.append(stripped)
        index += 1
    merged = " ".join(body_parts)
    wrapped = textwrap.fill(
        merged,
        width=MAX_WIDTH,
        initial_indent="  ",
        subsequent_indent="  ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped.splitlines(), index


def is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def is_new_logical_line(stripped: str) -> bool:
    if not stripped:
        return False
    if stripped.startswith("```"):
        return True
    if stripped.startswith("#"):
        return True
    if stripped == "---":
        return True
    if is_table_line(stripped):
        return True
    if stripped.startswith("<example>") or stripped.startswith("</example>"):
        return True
    if ORDERED_RE.match(stripped) or BULLET_RE.match(stripped):
        return True
    if REF_DEF_RE.match(stripped):
        return True
    return False


def merge_without_space(buffer: str, continuation: str) -> bool:
    """Join without space only for split markdown link URL paths."""
    base = buffer.rstrip()
    stripped = continuation.lstrip()
    if not base or not stripped:
        return False
    if stripped.startswith("/") and UNFINISHED_MD_LINK_TARGET.search(base):
        return True
    return False


def merge_soft_breaks(all_lines: list[str]) -> list[str]:
    reflowed_lines: list[str] = []
    index = 0
    is_inside_fence = False
    while index < len(all_lines):
        raw = all_lines[index]
        line = raw.rstrip("\n")
        if line.lstrip().startswith("```"):
            is_inside_fence = not is_inside_fence
            reflowed_lines.append(line)
            index += 1
            continue
        if is_inside_fence:
            reflowed_lines.append(line)
            index += 1
            continue
        if line.strip() == "":
            reflowed_lines.append(line)
            index += 1
            continue
        buffer_line = line
        index += 1
        while index < len(all_lines):
            next_raw = all_lines[index].rstrip("\n")
            if next_raw.strip() == "":
                break
            if next_raw.lstrip().startswith("```"):
                break
            stripped_next = next_raw.lstrip()
            if is_new_logical_line(stripped_next):
                break
            if merge_without_space(buffer_line, stripped_next):
                buffer_line = buffer_line.rstrip() + stripped_next
            else:
                buffer_line = f"{buffer_line.rstrip()} {stripped_next}"
            index += 1
        reflowed_lines.append(buffer_line)
    return reflowed_lines


def reflow_merged_line(line: str) -> list[str]:
    stripped = line.strip()
    if stripped == "":
        return [""]
    if stripped.startswith("```"):
        return [line]
    if stripped.startswith("#"):
        if len(stripped) <= MAX_WIDTH:
            return [stripped]
        title = stripped.lstrip("#").strip()
        level = len(stripped) - len(stripped.lstrip("#"))
        prefix = "#" * level + " "
        return textwrap.fill(
            title,
            width=MAX_WIDTH,
            initial_indent=prefix,
            subsequent_indent=prefix,
            break_long_words=False,
            break_on_hyphens=False,
        ).splitlines()
    if stripped == "---":
        return ["---"]
    if is_table_line(stripped):
        return [stripped]
    if stripped.startswith("</example>"):
        return [stripped]
    if stripped.startswith("<example>"):
        inner = stripped[len("<example>") :].strip()
        if not inner:
            return ["<example>"]
        tag = "<example> "
        subsequent = " " * len(tag)
        return textwrap.fill(
            " ".join(inner.split()),
            width=MAX_WIDTH,
            initial_indent=tag,
            subsequent_indent=subsequent,
            break_long_words=False,
            break_on_hyphens=False,
        ).splitlines()

    if REF_DEF_RE.match(stripped):
        return [stripped]

    ordered = ORDERED_RE.match(line)
    if ordered:
        return wrap_list_item(ordered.group(1), ordered.group(2), ordered.group(3))

    bullet = BULLET_RE.match(line)
    if bullet:
        return wrap_list_item(bullet.group(1), bullet.group(2), bullet.group(3))

    return wrap_paragraph_plain(stripped)


def reflow_markdown_body(all_lines: list[str]) -> list[str]:
    merged = merge_soft_breaks(all_lines)
    reflowed_lines: list[str] = []
    for each_line in merged:
        if each_line.strip() == "":
            reflowed_lines.append("")
            continue
        reflowed_lines.extend(reflow_merged_line(each_line))
    return reflowed_lines


def wrap_long_bash_fence_lines(all_lines: list[str]) -> list[str]:
    """Hard-wrap only ```bash fence bodies that still exceed MAX_WIDTH."""
    wrapped_lines: list[str] = []
    is_inside_bash_fence = False
    for each_line in all_lines:
        stripped = each_line.lstrip()
        if stripped.startswith("```"):
            if not is_inside_bash_fence:
                lang = stripped[3:].strip().lower()
                is_inside_bash_fence = lang == "bash"
            else:
                is_inside_bash_fence = False
            wrapped_lines.append(each_line)
            continue
        if is_inside_bash_fence and len(each_line) > MAX_WIDTH:
            indent_len = len(each_line) - len(each_line.lstrip())
            indent = each_line[:indent_len]
            if len(indent) + BASH_CONTINUATION_MARKER_WIDTH >= MAX_WIDTH:
                wrapped_lines.append(each_line)
                continue
            content = each_line.lstrip()
            wrapped_segments: list[str] = []
            rest = content
            while len(rest) > MAX_WIDTH - len(indent):
                room = MAX_WIDTH - len(indent) - BASH_CONTINUATION_MARKER_WIDTH
                window = rest[:room]
                break_at = window.rfind(" ")
                if break_at <= 0:
                    break_at = room
                piece = rest[:break_at].rstrip()
                rest = rest[break_at:].lstrip()
                wrapped_segments.append(indent + piece + " \\")
            if rest:
                wrapped_segments.append(indent + ("  " if wrapped_segments else "") + rest)
            wrapped_lines.extend(wrapped_segments)
        else:
            wrapped_lines.append(each_line)
    return wrapped_lines


def main() -> None:
    raw = SKILL_PATH.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit("expected YAML front matter starting with ---")

    out: list[str] = ["---"]
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.startswith("description: >-"):
            out.append(line)
            index += 1
            desc_lines, index = reflow_yaml_description_block(lines, index)
            out.extend(desc_lines)
            out.append("---")
            break
        out.append(line)
        index += 1

    body = reflow_markdown_body(lines[index:])
    body = wrap_long_bash_fence_lines(body)

    text = "\n".join(out + body) + "\n"
    SKILL_PATH.write_text(text, encoding="utf-8", newline="\n")

    all_lines = text.splitlines()
    long_rows = [(i, len(ln)) for i, ln in enumerate(all_lines, 1) if len(ln) > MAX_WIDTH]
    print("SKILL.md reflowed; lines:", len(all_lines))
    print("lines longer than %d: %d" % (MAX_WIDTH, len(long_rows)))
    if long_rows[:20]:
        print("first long:", long_rows[:20])


if __name__ == "__main__":
    main()
