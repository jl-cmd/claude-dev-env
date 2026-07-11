#!/usr/bin/env python3
"""Append an entry to implementation-notes.html under one of four sections.

Used by the `implement` skill. Creates the file with all four sections if it
does not exist; otherwise appends a new <li> under the requested section.

Usage:
    python append_note.py --section decisions --about "Where to write the file" --note "Wrote next to spec rather than CWD because spec path was known."
    python append_note.py --section questions --about "Auth model" --note "Spec didn't say whether sessions persist across restarts." --file ./notes.html
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

from implement_scripts_constants.notes_constants import DEFAULT_NOTES_FILENAME, HEADING_BY_SLUG


def _build_skeleton() -> str:
    section_blocks = "\n".join(
        f'  <section id="{each_slug}">\n    <h2>{each_heading}</h2>\n    <ul></ul>\n  </section>'
        for each_slug, each_heading in HEADING_BY_SLUG.items()
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        "  <title>Implementation notes</title>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Implementation notes</h1>\n"
        f"{section_blocks}\n"
        "</body>\n"
        "</html>\n"
    )


def _ensure_file(target: Path) -> str:
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        skeleton = _build_skeleton()
        target.write_text(skeleton, encoding="utf-8")
        return skeleton
    return target.read_text(encoding="utf-8")


def _render_entry(about: str, note: str) -> str:
    return f"<li><strong>{html.escape(about)}:</strong> {html.escape(note)}</li>"


def _insert_entry(document: str, slug: str, entry: str) -> str:
    open_marker = f'<section id="{slug}">'
    section_close_marker = "</section>"
    close_marker = "</ul>"
    section_start = document.find(open_marker)
    if section_start == -1:
        raise RuntimeError(
            f"section '{slug}' not found in file — the file may have been "
            f"edited by hand. Restore the four <section id=...> blocks or "
            f"delete the file so it can be regenerated."
        )
    section_end = document.find(section_close_marker, section_start)
    if section_end == -1:
        raise RuntimeError(
            f"section '{slug}' is missing its closing </section> — the file "
            f"may have been edited by hand."
        )
    close_at = document.find(close_marker, section_start, section_end)
    if close_at == -1:
        raise RuntimeError(
            f"section '{slug}' is missing its closing </ul> — the file may "
            f"have been edited by hand."
        )
    boundary = close_at
    while boundary > 0 and document[boundary - 1] in (" ", "\n"):
        boundary -= 1
    new_line = f"\n      {entry}"
    return document[:boundary] + new_line + "\n    " + document[close_at:]


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Append an entry to {DEFAULT_NOTES_FILENAME}.",
    )
    parser.add_argument(
        "--section",
        required=True,
        choices=sorted(HEADING_BY_SLUG.keys()),
        help="Which section to append under.",
    )
    parser.add_argument(
        "--about",
        required=True,
        help="Short label naming the part of the spec this entry relates to.",
    )
    parser.add_argument(
        "--note",
        required=True,
        help="The decision / deviation / tradeoff / question itself.",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_NOTES_FILENAME,
        help=(
            f"Path to the notes file. Defaults to ./{DEFAULT_NOTES_FILENAME} "
            f"in the current working directory."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Parse CLI arguments and append one entry to the notes file.

    Returns:
        Process exit code (0 on success).
    """
    arguments = _parse_arguments()
    target_path = Path(arguments.file).expanduser().resolve()
    document = _ensure_file(target_path)
    entry = _render_entry(arguments.about, arguments.note)
    updated = _insert_entry(document, arguments.section, entry)
    target_path.write_text(updated, encoding="utf-8")
    print(f"appended to [{arguments.section}] in {target_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
