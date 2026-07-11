"""Tests for append_note.

Covers:
- _build_skeleton emits a four-section HTML document keyed by every slug
- _ensure_file creates a fresh file on first call and round-trips on subsequent calls
- _render_entry HTML-escapes the about label and the note body
- _insert_entry puts the first <li> on its own line and keeps a 6-space indent across entries
- _insert_entry raises a descriptive RuntimeError when the section block is missing
- _insert_entry raises a descriptive RuntimeError when the closing </ul> is missing
- main appends through the CLI surface against a real on-disk file
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent


def _load_module() -> ModuleType:
    if str(_SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "append_note.py"
    spec = importlib.util.spec_from_file_location("append_note", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


append_note_module = _load_module()
HEADING_BY_SLUG = append_note_module.HEADING_BY_SLUG


def test_should_build_skeleton_with_every_section_slug() -> None:
    skeleton = append_note_module._build_skeleton()

    for each_slug, each_heading in HEADING_BY_SLUG.items():
        assert f'<section id="{each_slug}">' in skeleton
        assert f"<h2>{each_heading}</h2>" in skeleton
    assert skeleton.count("<ul></ul>") == len(HEADING_BY_SLUG)


def test_should_create_file_with_skeleton_on_first_ensure(tmp_path: Path) -> None:
    target = tmp_path / "subdir" / "implementation-notes.html"

    document = append_note_module._ensure_file(target)

    assert target.exists()
    assert document == target.read_text(encoding="utf-8")
    assert '<section id="decisions">' in document


def test_should_return_existing_content_on_subsequent_ensure(tmp_path: Path) -> None:
    target = tmp_path / "notes.html"
    custom_content = "<!doctype html><html><body>existing</body></html>\n"
    target.write_text(custom_content, encoding="utf-8")

    returned = append_note_module._ensure_file(target)

    assert returned == custom_content


def test_should_escape_html_metacharacters_in_about_and_note() -> None:
    entry = append_note_module._render_entry("a<b & c>d", "<script>x</script>")

    assert "<script>" not in entry
    assert "&lt;script&gt;" in entry
    assert "a&lt;b &amp; c&gt;d" in entry


def test_should_put_first_entry_on_its_own_line_inside_empty_ul() -> None:
    skeleton = append_note_module._build_skeleton()
    entry = append_note_module._render_entry("First", "alpha")

    after_first = append_note_module._insert_entry(skeleton, "decisions", entry)

    assert "<ul>      <li>" not in after_first
    assert "<ul>\n      <li>" in after_first


def test_should_keep_uniform_six_space_indent_across_multiple_entries() -> None:
    skeleton = append_note_module._build_skeleton()
    first_entry = append_note_module._render_entry("First", "alpha")
    second_entry = append_note_module._render_entry("Second", "beta")

    after_first = append_note_module._insert_entry(skeleton, "decisions", first_entry)
    after_second = append_note_module._insert_entry(after_first, "decisions", second_entry)

    decisions_section_start = after_second.index('<section id="decisions">')
    decisions_section_end = after_second.index("</section>", decisions_section_start)
    decisions_section = after_second[decisions_section_start:decisions_section_end]

    assert "          <li>" not in decisions_section
    assert decisions_section.count("\n      <li>") == 2


def test_should_raise_when_requested_section_is_absent() -> None:
    document_without_section = "<html><body></body></html>\n"
    entry = append_note_module._render_entry("x", "y")

    with pytest.raises(RuntimeError, match="section 'decisions' not found"):
        append_note_module._insert_entry(document_without_section, "decisions", entry)


def test_should_raise_when_closing_ul_is_missing() -> None:
    truncated_section = '<section id="decisions">\n    <h2>Design decisions</h2>\n    <ul>\n  </section>\n'
    entry = append_note_module._render_entry("x", "y")

    with pytest.raises(RuntimeError, match="missing its closing </ul>"):
        append_note_module._insert_entry(truncated_section, "decisions", entry)


def test_should_not_borrow_closing_ul_from_a_later_section() -> None:
    malformed_first_with_intact_second = (
        '<section id="decisions">\n'
        '    <h2>Design decisions</h2>\n'
        '    <ul>\n'
        '  </section>\n'
        '  <section id="deviations">\n'
        '    <h2>Deviations</h2>\n'
        '    <ul></ul>\n'
        '  </section>\n'
    )
    entry = append_note_module._render_entry("x", "y")

    with pytest.raises(RuntimeError, match="missing its closing </ul>"):
        append_note_module._insert_entry(malformed_first_with_intact_second, "decisions", entry)


def test_should_raise_when_closing_section_is_missing() -> None:
    section_without_close = '<section id="decisions">\n    <h2>Design decisions</h2>\n    <ul></ul>\n'
    entry = append_note_module._render_entry("x", "y")

    with pytest.raises(RuntimeError, match="missing its closing </section>"):
        append_note_module._insert_entry(section_without_close, "decisions", entry)


def test_should_append_through_cli_against_real_file(tmp_path: Path) -> None:
    target = tmp_path / "notes.html"
    script_path = _SCRIPTS_DIRECTORY / "append_note.py"

    first_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--section",
            "decisions",
            "--about",
            "First",
            "--note",
            "alpha",
            "--file",
            str(target),
        ],
        cwd=str(_SCRIPTS_DIRECTORY),
        capture_output=True,
        text=True,
        check=False,
    )
    second_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--section",
            "questions",
            "--about",
            "Q1",
            "--note",
            "<beta & gamma>",
            "--file",
            str(target),
        ],
        cwd=str(_SCRIPTS_DIRECTORY),
        capture_output=True,
        text=True,
        check=False,
    )

    assert first_run.returncode == 0, first_run.stderr
    assert second_run.returncode == 0, second_run.stderr
    output = target.read_text(encoding="utf-8")
    assert "<li><strong>First:</strong> alpha</li>" in output
    assert "<li><strong>Q1:</strong> &lt;beta &amp; gamma&gt;</li>" in output
