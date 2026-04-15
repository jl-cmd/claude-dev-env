"""Tests for sync-to-cursor.py: canonical docs copy, manifest, and truncation footer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import sync_to_cursor as mod
from sync_to_cursor.rules import _read_paths_glob

_SYNC_SCRIPT = _SCRIPTS_DIR / "sync-to-cursor.py"


def _minimal_rule_files(claude_rules: Path) -> None:
    claude_rules.mkdir(parents=True, exist_ok=True)
    (claude_rules / "code-standards.md").write_text(
        "# Code standards stub\n", encoding="utf-8"
    )
    (claude_rules / "tasklings-preferences.md").write_text(
        "---\npaths:\n  - \"Y:/x/**\"\n---\n\n# Tasklings\n",
        encoding="utf-8",
    )
    (claude_rules / "right-sized-engineering.md").write_text("# RSE\n", encoding="utf-8")
    (claude_rules / "bdd.md").write_text("# BDD\n", encoding="utf-8")
    (claude_rules / "testing.md").write_text("# Testing\n", encoding="utf-8")
    (claude_rules / "research-mode.md").write_text("# RM\n", encoding="utf-8")
    (claude_rules / "conservative-action.md").write_text("# CA\n", encoding="utf-8")
    (claude_rules / "explore-thoroughly.md").write_text("# ET\n", encoding="utf-8")


def _minimal_code_rules_and_test_quality(claude_docs: Path) -> tuple[bytes, bytes]:
    claude_docs.mkdir(parents=True, exist_ok=True)
    cr = b"## CORE PRINCIPLES\n\nalpha\n"
    tq = b"## Core Testing Principles\n\nbeta\n"
    (claude_docs / "CODE_RULES.md").write_bytes(cr)
    (claude_docs / "TEST_QUALITY.md").write_bytes(tq)
    return cr, tq


def test_limit_lines_footer_mentions_cursor_docs() -> None:
    long_body = "\n".join(f"line {index}" for index in range(mod.MAX_RULE_BODY_LINES + 5))
    out = mod._limit_lines(long_body, mod.MAX_RULE_BODY_LINES)
    assert ".cursor/docs" in out
    assert "synced reference" in out
    assert "~/.claude/docs" in out


def test_sync_canonical_docs_copies_byte_identical(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    docs = claude / "docs"
    cr, tq = _minimal_code_rules_and_test_quality(docs)
    mod._sync_canonical_docs(claude, cursor, dry_run=False, quiet=True)
    assert (cursor / "docs" / "CODE_RULES.md").read_bytes() == cr
    assert (cursor / "docs" / "TEST_QUALITY.md").read_bytes() == tq


def test_sync_canonical_docs_skips_missing_with_no_dst(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    (claude / "docs").mkdir(parents=True)
    (claude / "docs" / "CODE_RULES.md").write_text("x", encoding="utf-8")
    mod._sync_canonical_docs(claude, cursor, dry_run=False, quiet=True)
    assert (cursor / "docs" / "CODE_RULES.md").read_text(encoding="utf-8") == "x"
    assert not (cursor / "docs" / "TEST_QUALITY.md").is_file()


def test_check_fails_when_doc_source_changes_without_resync(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    _minimal_rule_files(claude / "rules")
    _minimal_code_rules_and_test_quality(claude / "docs")
    env = {**os.environ, "LLM_SETTINGS_ROOT": str(tmp_path)}
    subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--force"],
        env=env,
        check=True,
        cwd=str(_SCRIPTS_DIR),
    )
    (claude / "docs" / "CODE_RULES.md").write_bytes(b"changed\n")
    subprocess_result = subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--check"],
        env=env,
        cwd=str(_SCRIPTS_DIR),
    )
    assert subprocess_result.returncode != 0


def test_check_passes_after_resync(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    _minimal_rule_files(claude / "rules")
    _minimal_code_rules_and_test_quality(claude / "docs")
    env = {**os.environ, "LLM_SETTINGS_ROOT": str(tmp_path)}
    subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--force"],
        env=env,
        check=True,
        cwd=str(_SCRIPTS_DIR),
    )
    subprocess_result = subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--check"],
        env=env,
        cwd=str(_SCRIPTS_DIR),
    )
    assert subprocess_result.returncode == 0


def test_manifest_includes_docs_entries(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    _minimal_rule_files(claude / "rules")
    _minimal_code_rules_and_test_quality(claude / "docs")
    env = {**os.environ, "LLM_SETTINGS_ROOT": str(tmp_path)}
    subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--force"],
        env=env,
        check=True,
        cwd=str(_SCRIPTS_DIR),
    )
    manifest = json.loads((cursor / ".sync-manifest.json").read_text(encoding="utf-8"))
    assert "docs_entries" in manifest
    de = manifest["docs_entries"]
    assert "docs/CODE_RULES.md" in de
    assert "docs/TEST_QUALITY.md" in de
    assert "sources_hash" in de["docs/CODE_RULES.md"]
    assert "output_hash" in de["docs/CODE_RULES.md"]


def test_merge_code_standards_with_pointer_style_code_rules(tmp_path: Path) -> None:
    rules_directory = tmp_path / "rules"
    docs_directory = tmp_path / "docs"
    rules_directory.mkdir(parents=True, exist_ok=True)
    docs_directory.mkdir(parents=True, exist_ok=True)
    (rules_directory / "code-standards.md").write_text(
        "# Code standards stub\n\n- Use full words\n", encoding="utf-8"
    )
    (docs_directory / "CODE_RULES.md").write_text(
        "# CODE_RULES pointer: canonical code-quality policy lives in"
        " `~/.claude/system-prompts/software-engineer.xml` under `<code_quality>`.\n",
        encoding="utf-8",
    )
    merged = mod.merge_code_standards(
        (rules_directory / "code-standards.md", docs_directory / "CODE_RULES.md")
    )
    assert merged.strip(), "output must not be empty for pointer-style CODE_RULES.md"
    assert mod.CODE_RULES_POINTER_FALLBACK in merged


def test_sync_canonical_docs_deletes_stale_copy_when_source_removed(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    _minimal_code_rules_and_test_quality(claude / "docs")
    mod._sync_canonical_docs(claude, cursor, dry_run=False, quiet=True)
    assert (cursor / "docs" / "CODE_RULES.md").is_file()
    (claude / "docs" / "CODE_RULES.md").unlink()
    mod._sync_canonical_docs(claude, cursor, dry_run=False, quiet=True)
    assert not (cursor / "docs" / "CODE_RULES.md").is_file()


def test_dry_run_does_not_create_output_directory(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    _minimal_rule_files(claude / "rules")
    _minimal_code_rules_and_test_quality(claude / "docs")
    env = {**os.environ, "LLM_SETTINGS_ROOT": str(tmp_path)}
    subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--dry-run", "--quiet"],
        env=env,
        check=True,
        cwd=str(_SCRIPTS_DIR),
    )
    assert not (cursor / "rules").exists(), "--dry-run must not create the output directory"


def test_check_skips_optional_mapping_when_source_missing(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    cursor = tmp_path / ".cursor"
    _minimal_rule_files(claude / "rules")
    _minimal_code_rules_and_test_quality(claude / "docs")
    env = {**os.environ, "LLM_SETTINGS_ROOT": str(tmp_path)}
    subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--force"],
        env=env,
        check=True,
        cwd=str(_SCRIPTS_DIR),
    )
    # Remove an optional source (tasklings-preferences has always_apply=False)
    (claude / "rules" / "tasklings-preferences.md").unlink()
    subprocess_result = subprocess.run(
        [sys.executable, str(_SYNC_SCRIPT), "--check"],
        env=env,
        cwd=str(_SCRIPTS_DIR),
    )
    assert subprocess_result.returncode == 0, "--check must pass when only optional sources are missing"


def test_tasklings_glob_derived_from_frontmatter(tmp_path: Path) -> None:
    rules_directory = tmp_path / "rules"
    rules_directory.mkdir(parents=True)
    (rules_directory / "tasklings-preferences.md").write_text(
        '---\npaths:\n  - "Y:/MyProject/**"\n  - "Z:/Other/**"\n---\n\n# Tasklings\n',
        encoding="utf-8",
    )
    glob_value = _read_paths_glob(rules_directory / "tasklings-preferences.md")
    assert glob_value == "Y:/MyProject/**,Z:/Other/**"


def test_merge_reference_headers_point_at_cursor_docs(tmp_path: Path) -> None:
    rules_directory = tmp_path / "rules"
    docs_directory = tmp_path / "docs"
    rules_directory.mkdir(parents=True, exist_ok=True)
    docs_directory.mkdir(parents=True, exist_ok=True)
    (rules_directory / "code-standards.md").write_text("# CS\n", encoding="utf-8")
    cr_body = "\n\n".join(
        f"## {t}\n\nbody"
        for t in [
            "COMMENT PRESERVATION (ABSOLUTE RULE)",
            "CORE PRINCIPLES",
            "⚡ HOOK-ENFORCED RULES",
            "4. CONFIG LOCATIONS",
            "5. NO ABBREVIATIONS",
            "6. COMPLETE TYPE HINTS",
            "9. SELF-CONTAINED COMPONENTS",
        ]
    )
    (docs_directory / "CODE_RULES.md").write_text(cr_body, encoding="utf-8")
    merged = mod.merge_code_standards(
        (rules_directory / "code-standards.md", docs_directory / "CODE_RULES.md")
    )
    assert ".cursor/docs/CODE_RULES.md" in merged

    (rules_directory / "testing.md").write_text("# T\n", encoding="utf-8")
    tq_body = "\n\n".join(
        f"## {t}\n\nbody"
        for t in [
            "Delete Useless Tests",
            "Test Dependencies MUST FAIL",
            "Core Testing Principles",
            "React Testing Patterns",
            "Test File Organization",
        ]
    )
    (docs_directory / "TEST_QUALITY.md").write_text(tq_body, encoding="utf-8")
    merged_tq = mod.merge_test_quality(
        (rules_directory / "testing.md", docs_directory / "TEST_QUALITY.md")
    )
    assert ".cursor/docs/TEST_QUALITY.md" in merged_tq
