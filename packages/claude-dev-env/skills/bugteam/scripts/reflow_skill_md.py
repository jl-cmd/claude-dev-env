"""Reflow packages/claude-dev-env/skills/bugteam/SKILL.md to 80 columns.

Merge soft line breaks outside fenced blocks (space join; URL path fragments
joined without a space only inside unfinished markdown link targets), then
wrap with textwrap. Preserves fenced blocks verbatim.

Same algorithm as ``packages/claude-dev-env/skills/pr-converge/scripts/reflow_skill_md.py``
from https://github.com/jl-cmd/claude-code-config/pull/349 (branch
``cursor/pr-converge-skill-line-wrap-ecd1``); ``SKILL_PATH`` points at bugteam
``SKILL.md``. Link reference definitions (``[id]: url``) are treated as logical
line starts so they are not merged with prior paragraphs.

Run: python3 packages/claude-dev-env/skills/bugteam/scripts/reflow_skill_md.py
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

MAX_WIDTH = 80
SKILL_PATH = Path(__file__).resolve().parent.parent / "SKILL.md"

ORDERED_RE = re.compile(r"^(\s*)(\d+\.\s)(.*)$")
BULLET_RE = re.compile(r"^(\s*)([-*]\s)(.*)$")
UNFINISHED_MD_LINK_TARGET = re.compile(r"\]\([^)]*$")


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


def reflow_yaml_description_block(lines: list[str], body_start: int) -> tuple[list[str], int]:
    body_parts: list[str] = []
    index = body_start
    while index < len(lines):
        line = lines[index]
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


def is_link_reference_definition(stripped: str) -> bool:
    return bool(re.match(r"^\[[^\]]+\]:\s+\S", stripped))


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
    if is_link_reference_definition(stripped):
        return True
    if ORDERED_RE.match(stripped) or BULLET_RE.match(stripped):
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


def merge_soft_breaks(lines: list[str]) -> list[str]:
    output: list[str] = []
    index = 0
    in_fence = False
    while index < len(lines):
        raw = lines[index]
        line = raw.rstrip("\n")
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            output.append(line)
            index += 1
            continue
        if in_fence:
            output.append(line)
            index += 1
            continue
        if line.strip() == "":
            output.append(line)
            index += 1
            continue
        buffer_line = line
        index += 1
        while index < len(lines):
            next_raw = lines[index].rstrip("\n")
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
        output.append(buffer_line)
    return output


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
    if is_link_reference_definition(stripped):
        return [stripped]
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

    ordered = ORDERED_RE.match(line)
    if ordered:
        return wrap_list_item(ordered.group(1), ordered.group(2), ordered.group(3))

    bullet = BULLET_RE.match(line)
    if bullet:
        return wrap_list_item(bullet.group(1), bullet.group(2), bullet.group(3))

    return wrap_paragraph_plain(stripped)


def reflow_markdown_body(lines: list[str]) -> list[str]:
    merged = merge_soft_breaks(lines)
    output: list[str] = []
    for each_line in merged:
        if each_line.strip() == "":
            output.append("")
            continue
        output.extend(reflow_merged_line(each_line))
    return output


def wrap_long_bash_fence_lines(lines: list[str]) -> list[str]:
    """Hard-wrap only ```bash fence bodies that still exceed MAX_WIDTH."""
    output: list[str] = []
    in_bash_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if not in_bash_fence:
                lang = stripped[3:].strip().lower()
                in_bash_fence = lang == "bash"
            else:
                in_bash_fence = False
            output.append(line)
            continue
        if in_bash_fence and len(line) > MAX_WIDTH:
            indent_len = len(line) - len(line.lstrip())
            indent = line[:indent_len]
            content = line.lstrip()
            wrapped_segments: list[str] = []
            rest = content
            while len(rest) > MAX_WIDTH - len(indent):
                room = MAX_WIDTH - len(indent) - 2
                window = rest[:room]
                break_at = window.rfind(" ")
                if break_at <= 0:
                    break_at = room
                piece = rest[:break_at].rstrip()
                rest = rest[break_at:].lstrip()
                wrapped_segments.append(indent + piece + " \\")
            if rest:
                wrapped_segments.append(indent + ("  " if wrapped_segments else "") + rest)
            output.extend(wrapped_segments)
        else:
            output.append(line)
    return output


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
