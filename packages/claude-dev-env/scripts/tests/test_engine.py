"""Tests for sync_to_cursor engine CLI roots."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sync_to_cursor.engine import run as run_sync_to_cursor

_CODE_STANDARDS_SECTION_ORDER = (
    "COMMENT PRESERVATION",
    "CORE PRINCIPLES",
    "⚡ HOOK-ENFORCED RULES",
    "3. REUSE CONSTANTS / 4. CONFIG LOCATIONS",
    "5. NO ABBREVIATIONS",
    "6. COMPLETE TYPE HINTS",
    "9. SELF-CONTAINED COMPONENTS",
)
_TEST_QUALITY_SECTION_ORDER = (
    "Delete Useless Tests",
    "Test Dependencies MUST FAIL",
    "Core Testing Principles",
    "React Testing Patterns",
    "Test File Organization",
)


def _write_minimal_curated_rules(rules_directory: Path) -> None:
    rules_directory.mkdir(parents=True, exist_ok=True)
    (rules_directory / "code-standards.md").write_text(
        "# Code standards stub\n", encoding="utf-8"
    )
    (rules_directory / "tasklings-preferences.md").write_text(
        '---\npaths:\n  - "Y:/x/**"\n---\n\n# Tasklings\n',
        encoding="utf-8",
    )
    (rules_directory / "bdd.md").write_text("# BDD\n", encoding="utf-8")
    (rules_directory / "testing.md").write_text(
        '---\npaths:\n  - "**/test_*.py"\n---\n\n# Testing\n',
        encoding="utf-8",
    )
    (rules_directory / "research-mode.md").write_text("# RM\n", encoding="utf-8")
    (rules_directory / "conservative-action.md").write_text("# CA\n", encoding="utf-8")
    (rules_directory / "explore-thoroughly.md").write_text("# ET\n", encoding="utf-8")


def _write_minimal_docs(docs_directory: Path) -> None:
    docs_directory.mkdir(parents=True, exist_ok=True)
    (docs_directory / "CODE_RULES.md").write_text(
        "\n\n".join(f"## {title}\n\nalpha" for title in _CODE_STANDARDS_SECTION_ORDER)
        + "\n",
        encoding="utf-8",
    )
    (docs_directory / "TEST_QUALITY.md").write_text(
        "\n\n".join(f"## {title}\n\nbeta" for title in _TEST_QUALITY_SECTION_ORDER)
        + "\n",
        encoding="utf-8",
    )


def test_explicit_roots_write_stem_named_mdc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude = tmp_path / "claude-home"
    cursor = tmp_path / "cursor-home"
    _write_minimal_curated_rules(claude / "rules")
    _write_minimal_docs(claude / "docs")
    (claude / "rules" / "plain-language.md").write_text(
        "# Plain language\n\nUse short sentences.\n",
        encoding="utf-8",
    )
    (claude / "rules" / "CLAUDE.md").write_text("# Inventory\n", encoding="utf-8")
    monkeypatch.delenv("LLM_SETTINGS_ROOT", raising=False)
    assert cursor.exists() is False
    assert (
        run_sync_to_cursor(
            [
                "--force",
                "--claude-root",
                str(claude),
                "--cursor-root",
                str(cursor),
            ]
        )
        == 0
    )
    generated = (cursor / "rules" / "plain-language.mdc").read_text(encoding="utf-8")
    assert 'description: "Plain language"' in generated
    assert "alwaysApply: true" in generated
    assert "Use short sentences." in generated
    assert not (cursor / "rules" / "CLAUDE.mdc").is_file()


def test_explicit_roots_require_both_flags(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        run_sync_to_cursor(["--force", "--claude-root", str(tmp_path)])
