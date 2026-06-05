"""Tests pinning build_audit_prompt's emitted A-N category taxonomy."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from xml.etree.ElementTree import Element

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from skills_pr_loop_constants.path_resolver_constants import (
    ALL_AUDIT_CATEGORY_ENTRIES,
)

_CATEGORY_RUBRICS_DIR = _SCRIPTS_DIR.parents[3] / "audit-rubrics" / "category_rubrics"
_HEADING_PATTERN = re.compile(r"^# Category ([A-N]) — (.+)$")


def _load_build_audit_prompt() -> ModuleType:
    module_path = _SCRIPTS_DIR / "build_audit_prompt.py"
    spec = importlib.util.spec_from_file_location("build_audit_prompt", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_audit_prompt"] = module
    spec.loader.exec_module(module)
    return module


build_audit_prompt = _load_build_audit_prompt()


def _rubric_label_by_letter() -> dict[str, str]:
    assert _CATEGORY_RUBRICS_DIR.is_dir(), f"Missing rubric directory: {_CATEGORY_RUBRICS_DIR}"
    all_labels: dict[str, str] = {}
    for each_rubric_file in sorted(_CATEGORY_RUBRICS_DIR.glob("category-*.md")):
        all_rubric_lines = each_rubric_file.read_text(encoding="utf-8").splitlines()
        assert all_rubric_lines, f"Empty rubric file: {each_rubric_file}"
        each_match = _HEADING_PATTERN.match(all_rubric_lines[0])
        assert each_match is not None, f"Heading pattern not matched in {each_rubric_file}"
        all_labels[each_match.group(1)] = each_match.group(2)
    return all_labels


def _build_audit_root() -> Element:
    return build_audit_prompt.build_audit_prompt_xml(
        owner="jl-cmd",
        repo="claude-code-config",
        pr_number=422,
        loop=1,
        head_ref="feat/branch",
        base_ref="main",
        worktree_path=Path("/tmp/bugteam-pr-422/worktree"),
        run_temp_dir=Path("/tmp/bugteam-pr-422"),
    )


def test_bug_categories_carry_ids_a_through_n_in_order() -> None:
    root = _build_audit_root()
    bug_categories = root.find("bug_categories")
    assert bug_categories is not None
    all_emitted_ids = [each_category.get("id") for each_category in bug_categories]
    all_expected_ids = list("ABCDEFGHIJKLMN")
    assert all_emitted_ids == all_expected_ids


def test_emitted_category_labels_match_constant_entries() -> None:
    root = _build_audit_root()
    bug_categories = root.find("bug_categories")
    assert bug_categories is not None
    label_by_id = {
        each_category.get("id"): each_category.text for each_category in bug_categories
    }
    for each_category_id, each_category_label in ALL_AUDIT_CATEGORY_ENTRIES:
        assert label_by_id[each_category_id] == each_category_label


def test_category_labels_match_rubric_file_headings() -> None:
    assert dict(ALL_AUDIT_CATEGORY_ENTRIES) == _rubric_label_by_letter()


def test_rubric_reference_element_names_category_rubrics_directory() -> None:
    root = _build_audit_root()
    rubric_reference = root.find("rubric_reference")
    assert rubric_reference is not None
    assert rubric_reference.text is not None
    assert "audit-rubrics/category_rubrics" in rubric_reference.text
