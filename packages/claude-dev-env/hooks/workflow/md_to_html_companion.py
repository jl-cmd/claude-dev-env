#!/usr/bin/env python3
"""PostToolUse hook: generates a companion .html from a .md file after write.

The .md serves as a first draft; the .html is a 2nd-pass refinement with
dark-mode styling that also validates the .md structure.
See https://thariqs.github.io/html-effectiveness/
"""

import json
import logging
import os
import re
import sys
from html import escape
from pathlib import Path
from urllib.parse import urlparse


logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(message)s")

_hook_dir = str(Path(__file__).resolve().parent.parent)
if _hook_dir not in sys.path:
    sys.path.insert(0, _hook_dir)

_blocking_dir = str(Path(__file__).resolve().parent.parent / "blocking")
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)

from hooks_constants.html_companion_constants import (  # noqa: E402
    BLOCKED_URL_SCHEMES,
    CSS_ACCENT_COLOR,
    CSS_BG_COLOR,
    CSS_BODY_PADDING,
    CSS_BORDER_COLOR,
    CSS_CODE_SIZE,
    CSS_FG_COLOR,
    CSS_H1_SIZE,
    CSS_H2_SIZE,
    CSS_H3_SIZE,
    CSS_LINE_HEIGHT,
    CSS_MAX_WIDTH,
    CSS_MUTED_COLOR,
    CSS_STRONG_COLOR,
    CSS_SURFACE_COLOR,
    CSS_TABLE_WIDTH,
    CSS_TH_WEIGHT,
)
from md_path_exemptions import is_exempt_path  # noqa: E402


def _md_to_html(markdown_text: str) -> str:
    text = markdown_text.strip()
    if not text:
        return ""

    all_lines = text.split("\n")
    all_output_lines: list[str] = []
    is_in_code_block = False
    is_in_unordered_list = False
    is_in_ordered_list = False
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            all_output_lines.append("<p>" + "\n".join(paragraph_buffer) + "</p>")
            paragraph_buffer.clear()

    def close_lists() -> None:
        nonlocal is_in_unordered_list, is_in_ordered_list
        if is_in_unordered_list:
            all_output_lines.append("</ul>")
            is_in_unordered_list = False
        if is_in_ordered_list:
            all_output_lines.append("</ol>")
            is_in_ordered_list = False

    for each_line in all_lines:
        if each_line.startswith("```"):
            if is_in_code_block:
                all_output_lines.append("</code></pre>")
                is_in_code_block = False
            else:
                flush_paragraph()
                close_lists()
                language = each_line[3:].strip()
                if language and re.match(r"^[A-Za-z0-9_+#-]+$", language):
                    all_output_lines.append(
                        f'<pre><code class="language-{language}">'
                    )
                else:
                    all_output_lines.append("<pre><code>")
                is_in_code_block = True
            continue

        if is_in_code_block:
            all_output_lines.append(escape(each_line))
            continue

        stripped = each_line.strip()
        if not stripped:
            flush_paragraph()
            close_lists()
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            close_lists()
            all_output_lines.append(f"<h1>{_inline_format(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            flush_paragraph()
            close_lists()
            all_output_lines.append(f"<h2>{_inline_format(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            flush_paragraph()
            close_lists()
            all_output_lines.append(f"<h3>{_inline_format(stripped[4:])}</h3>")
        elif stripped.startswith("#### "):
            flush_paragraph()
            close_lists()
            all_output_lines.append(f"<h4>{_inline_format(stripped[5:])}</h4>")
        elif stripped.startswith("##### "):
            flush_paragraph()
            close_lists()
            all_output_lines.append(f"<h5>{_inline_format(stripped[6:])}</h5>")
        elif stripped.startswith("###### "):
            flush_paragraph()
            close_lists()
            all_output_lines.append(f"<h6>{_inline_format(stripped[7:])}</h6>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            if is_in_ordered_list:
                all_output_lines.append("</ol>")
                is_in_ordered_list = False
            if not is_in_unordered_list:
                all_output_lines.append("<ul>")
                is_in_unordered_list = True
            all_output_lines.append(f"<li>{_inline_format(stripped[2:])}</li>")
        elif re.match(r"^\d+\.\s", stripped):
            flush_paragraph()
            if is_in_unordered_list:
                all_output_lines.append("</ul>")
                is_in_unordered_list = False
            if not is_in_ordered_list:
                all_output_lines.append("<ol>")
                is_in_ordered_list = True
            content = re.sub(r"^\d+\.\s", "", stripped)
            all_output_lines.append(f"<li>{_inline_format(content)}</li>")
        elif stripped == "---":
            flush_paragraph()
            close_lists()
            all_output_lines.append("<hr>")
        elif stripped.startswith("> "):
            flush_paragraph()
            close_lists()
            all_output_lines.append(
                f"<blockquote>{_inline_format(stripped[2:])}</blockquote>"
            )
        else:
            paragraph_buffer.append(_inline_format(stripped))

    if is_in_code_block:
        all_output_lines.append("</code></pre>")
    close_lists()
    flush_paragraph()

    return "\n".join(all_output_lines)


def _placeholder(
    match: re.Match, storage: list, open_tag: str, close_tag: str
) -> str:
    placeholder = f"\x00CODE{len(storage)}\x00"
    storage.append((placeholder, f"{open_tag}{match.group(1)}{close_tag}"))
    return placeholder


def _inline_format(text: str) -> str:
    text = escape(text)

    code_placeholders: list[tuple[str, str]] = []
    text = re.sub(
        r"`([^`]+)`",
        lambda m: _placeholder(m, code_placeholders, "<code>", "</code>"),
        text,
    )

    link_placeholders: list[tuple[str, str, str]] = []

    def _save_link(match: re.Match) -> str:
        link_text = match.group("text")
        url = match.group("url").strip()
        parsed_url = urlparse(url)
        if parsed_url.scheme.lower() in BLOCKED_URL_SCHEMES:
            url = ""
        placeholder = f"\x00LINK{len(link_placeholders)}\x00"
        link_placeholders.append((placeholder, url, link_text))
        return placeholder

    text = re.sub(
        r"\[(?P<text>[^\]]+)\]\((?P<url>(?:[^)(]+|\([^)(]*\))*)\)",
        _save_link,
        text,
    )

    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    for placeholder, url, link_text in link_placeholders:
        if url == "":
            text = text.replace(placeholder, link_text)
        else:
            text = text.replace(placeholder, f'<a href="{url}">{link_text}</a>')
    for placeholder, content in code_placeholders:
        text = text.replace(placeholder, content)
    return text


def _extract_title(markdown_text: str) -> str:
    for each_line in markdown_text.strip().split("\n"):
        stripped = each_line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "Document"


def _html_template(title: str, body: str) -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: rgb({bg}); color: rgb({fg}); line-height: {line_height};
    padding: {body_padding}; max-width: {max_width}; margin: 0 auto;
  }}
  h1 {{ font-size: {h1_size}; border-bottom: 1px solid rgb({border}); padding-bottom: 0.5rem; margin: 1.5rem 0 1rem; }}
  h2 {{ font-size: {h2_size}; margin: 1.25rem 0 0.75rem; color: rgb({accent}); }}
  h3 {{ font-size: {h3_size}; margin: 1rem 0 0.5rem; }}
  p {{ margin: 0.75rem 0; }}
  a {{ color: rgb({accent}); }}
  code {{
    font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: {code_size};
    background: rgb({surface}); padding: 0.15em 0.35em; border-radius: 3px;
  }}
  pre {{
    background: rgb({surface}); border: 1px solid rgb({border});
    border-radius: 6px; padding: 1rem; overflow-x: auto; margin: 0.75rem 0;
  }}
  pre code {{ background: none; padding: 0; }}
  ul, ol {{ padding-left: 1.5rem; margin: 0.5rem 0; }}
  li {{ margin: 0.25rem 0; }}
  strong {{ color: rgb({strong}); }}
  table {{ width: {table_width}; border-collapse: collapse; margin: 0.75rem 0; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border: 1px solid rgb({border}); }}
  th {{ background: rgb({surface}); font-weight: {th_weight}; }}
  hr {{ border: none; border-top: 1px solid rgb({border}); margin: 1.5rem 0; }}
  blockquote {{
    border-left: 3px solid rgb({accent}); padding-left: 1rem;
    color: rgb({muted}); margin: 0.75rem 0;
  }}
</style>
</head>
<body>
{body}
</body>
</html>""".format(
        title=title,
        body=body,
        bg=CSS_BG_COLOR,
        fg=CSS_FG_COLOR,
        border=CSS_BORDER_COLOR,
        accent=CSS_ACCENT_COLOR,
        muted=CSS_MUTED_COLOR,
        surface=CSS_SURFACE_COLOR,
        strong=CSS_STRONG_COLOR,
        line_height=CSS_LINE_HEIGHT,
        body_padding=CSS_BODY_PADDING,
        max_width=CSS_MAX_WIDTH,
        h1_size=CSS_H1_SIZE,
        h2_size=CSS_H2_SIZE,
        h3_size=CSS_H3_SIZE,
        code_size=CSS_CODE_SIZE,
        table_width=CSS_TABLE_WIDTH,
        th_weight=CSS_TH_WEIGHT,
    )


def main() -> None:
    """Process a PostToolUse hook payload from stdin.

    Reads JSON with tool_name and tool_input.file_path from stdin.
    When file_path is a .md file outside .claude/, generates a companion
    .html file alongside it.

    Args:
        (reads from sys.stdin — no function arguments)

    Returns:
        None — exits 0 on success or when no action is needed.
    """
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path or not file_path.lower().endswith(".md"):
        sys.exit(0)

    if is_exempt_path(file_path):
        sys.exit(0)

    if not os.path.exists(file_path):
        sys.exit(0)

    try:
        with open(file_path, encoding="utf-8") as f:
            md_content = f.read()
    except OSError:
        sys.exit(0)

    if not md_content.strip():
        sys.exit(0)

    title = escape(_extract_title(md_content))
    html_body = _md_to_html(md_content)
    html_content = _html_template(title=title, body=html_body)

    html_path = os.path.splitext(file_path)[0] + ".html"
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except OSError:
        logging.warning(
            "md_to_html_companion: failed to write %s", html_path
        )

    sys.exit(0)


if __name__ == "__main__":
    main()