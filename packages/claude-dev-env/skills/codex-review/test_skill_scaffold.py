"""Scaffold contract tests for the codex-review skill package."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path


SKILL_DIRECTORY = Path(__file__).resolve().parent
SKILL_PATH = SKILL_DIRECTORY / "SKILL.md"
PACKAGE_MAP_PATH = SKILL_DIRECTORY / "CLAUDE.md"
REFERENCE_DIRECTORY = SKILL_DIRECTORY / "reference"
PACKAGE_ROOT = SKILL_DIRECTORY.parents[1]
PYPROJECT_PATH = PACKAGE_ROOT / "pyproject.toml"
EVER_SHIPPED_SKILLS_PATH = PACKAGE_ROOT / "bin" / "ever-shipped-skills.mjs"
CONSTANTS_PACKAGE_NAME = "codex_review_scripts_constants"
CONSTANTS_PACKAGE_DIR = "skills/codex-review/scripts/codex_review_scripts_constants"
SKILL_NAME = "codex-review"
MAXIMUM_SKILL_BODY_LINE_COUNT = 500


def _read_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_constants_package_imports() -> None:
    constants_package = importlib.import_module(CONSTANTS_PACKAGE_NAME)

    assert constants_package.__name__ == CONSTANTS_PACKAGE_NAME


def test_pyproject_registers_constants_package() -> None:
    parsed_pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    setuptools_table = parsed_pyproject["tool"]["setuptools"]
    all_packages = setuptools_table["packages"]
    package_directory_by_name = setuptools_table["package-dir"]

    assert CONSTANTS_PACKAGE_NAME in all_packages
    assert package_directory_by_name[CONSTANTS_PACKAGE_NAME] == CONSTANTS_PACKAGE_DIR


def test_ever_shipped_skills_lists_codex_review() -> None:
    ever_shipped_text = EVER_SHIPPED_SKILLS_PATH.read_text(encoding="utf-8")

    assert f"'{SKILL_NAME}'" in ever_shipped_text


def test_skill_md_exists_with_trigger_description() -> None:
    skill_text = _read_skill_text()

    assert "name: codex-review" in skill_text
    assert "/codex-review" in skill_text
    assert "codex review" in skill_text
    assert "run codex review" in skill_text
    assert "babysit codex review" in skill_text
    assert "codex as a PR reviewer" in skill_text


def test_skill_composes_opt_out_and_fix_protocol_by_name() -> None:
    skill_text = _read_skill_text()

    assert "reviews_disabled.py" in skill_text
    assert "--reviewer codex" in skill_text
    assert "pr-fix-protocol" in skill_text
    assert "reviewer-gates" in skill_text


def test_skill_documents_non_zero_one_gate_exit_path() -> None:
    skill_text = _read_skill_text()

    assert "--reviewer codex" in skill_text
    assert "Any other exit" in skill_text
    assert "parse failure" in skill_text
    assert "blocker" in skill_text


def test_skill_documents_flow_skeleton() -> None:
    skill_text = _read_skill_text()
    skill_text_lower = skill_text.lower()

    assert "shape probe" in skill_text_lower
    assert "wrapper" in skill_text_lower
    assert "classif" in skill_text_lower
    assert "`down`" in skill_text
    assert "`clean`" in skill_text
    assert "`findings`" in skill_text
    assert "`codex_down`" in skill_text
    assert "base branch" in skill_text_lower
    assert "uncommitted" in skill_text_lower


def test_skill_body_stays_under_line_cap() -> None:
    skill_line_count = len(_read_skill_text().splitlines())

    assert skill_line_count < MAXIMUM_SKILL_BODY_LINE_COUNT


def test_package_map_claude_md_exists() -> None:
    package_map_text = PACKAGE_MAP_PATH.read_text(encoding="utf-8")

    assert "codex-review" in package_map_text
    assert "SKILL.md" in package_map_text
    assert "reference/" in package_map_text
    assert "cli-contract.md" in package_map_text
    assert "codex_down" in package_map_text


def test_reference_shell_pages_exist() -> None:
    assert (REFERENCE_DIRECTORY / "cli-contract.md").is_file()
    assert (REFERENCE_DIRECTORY / "loop-integration.md").is_file()
    assert (REFERENCE_DIRECTORY / "CLAUDE.md").is_file()


def test_constants_package_directory_exists() -> None:
    constants_directory = SKILL_DIRECTORY / "scripts" / "codex_review_scripts_constants"

    assert (constants_directory / "__init__.py").is_file()
    assert (constants_directory / "CLAUDE.md").is_file()
