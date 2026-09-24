"""Behavioral tests for the banned emphasis word detector."""

from __future__ import annotations

from pathlib import Path

from banned_prose_words import (
    banned_prose_words_in_tree,
    find_banned_prose_words,
    governed_paths,
    governs_path,
    prose_lines,
)


def test_prose_occurrence_is_reported_with_its_line() -> None:
    all_hits = find_banned_prose_words("First line.\nThe real cause is a timeout.\n")
    assert [(each_line, each_word) for each_line, _column, each_word in all_hits] == [
        (2, "real")
    ]


def test_every_banned_form_is_reported() -> None:
    document_text = (
        "It is real.\n"
        "It is really late.\n"
        "A real-world case.\n"
        "The actual value.\n"
        "It actually ran.\n"
        "A genuine failure.\n"
        "It genuinely ran.\n"
        "It truly ran.\n"
        "The true cause.\n"
    )
    all_words = {each_word for _line, _column, each_word in
                 find_banned_prose_words(document_text)}
    assert all_words == {
        "real",
        "really",
        "real-world",
        "actual",
        "actually",
        "genuine",
        "genuinely",
        "truly",
        "true",
    }


def test_code_spans_and_paths_carry_no_finding() -> None:
    document_text = (
        "Read `actual_value` from the map.\n"
        "```python\n"
        "actual = compute()\n"
        "```\n"
        "    while True:\n"
        "See docs/really-long-name.md for the table.\n"
        "The flag reads always_apply: true.\n"
    )
    assert find_banned_prose_words(document_text) == []


def test_predicative_true_carries_no_finding() -> None:
    document_text = (
        "The condition is true when the port answers.\n"
        "A branch that is always true never runs the other arm.\n"
    )
    assert find_banned_prose_words(document_text) == []


def test_prose_lines_blank_code_and_keep_the_line_count() -> None:
    document_text = "Prose here.\n```python\nactual = 1\n```\nMore prose.\n"
    assert prose_lines(document_text) == ["Prose here.", "", "", "", "More prose."]


def test_governed_paths_lists_the_shipped_surfaces(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "one.md").write_text("Prose.\n", encoding="utf-8")
    (tmp_path / "rules-archived").mkdir()
    (tmp_path / "rules-archived" / "two.md").write_text("Prose.\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "three.py").write_text("x = 1\n", encoding="utf-8")
    assert governed_paths(tmp_path) == ["rules/one.md"]


def test_governed_paths_cover_instruction_surfaces_and_skip_archives() -> None:
    assert governs_path("rules/git-workflow.md")
    assert governs_path(".agents/skills/eli5/SKILL.md")
    assert governs_path("audit-rubrics/prompts/category-o-docstring-vs-impl-drift.md")
    assert governs_path("system-prompts/software-engineer.xml")
    assert not governs_path("rules-archived/manifest.md")
    assert not governs_path("scripts/banned_prose_words.py")
    assert not governs_path("CHANGELOG.md")


def test_shipped_instruction_surfaces_carry_no_banned_word() -> None:
    package_root = Path(__file__).resolve().parent.parent.parent
    all_hits = banned_prose_words_in_tree(package_root)
    report = "\n".join(
        f"{each_path}:{each_line}:{each_column} {each_word}"
        for each_path, each_line, each_column, each_word in all_hits[:40]
    )
    assert not all_hits, f"{len(all_hits)} banned words on shipped surfaces:\n{report}"
