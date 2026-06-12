"""Tests pinning build_audit_prompt's emitted A-P category taxonomy."""

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
_HEADING_PATTERN = re.compile(r"^# Category ([A-P]) — (.+)$")


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


def test_context_and_scope_render_paths_with_forward_slashes() -> None:
    root = build_audit_prompt.build_audit_prompt_xml(
        owner="jl-cmd",
        repo="claude-code-config",
        pr_number=376,
        loop=1,
        head_ref="feat/branch",
        base_ref="main",
        worktree_path=Path("C:/Users/jon/AppData/Local/Temp/bugteam-pr-376/worktree"),
        run_temp_dir=Path("C:/Users/jon/AppData/Local/Temp/bugteam-pr-376"),
    )
    context = root.find("context")
    assert context is not None
    worktree_text = context.findtext("worktree_path")
    run_temp_text = context.findtext("run_temp_dir")
    assert worktree_text == "C:/Users/jon/AppData/Local/Temp/bugteam-pr-376/worktree"
    assert run_temp_text == "C:/Users/jon/AppData/Local/Temp/bugteam-pr-376"
    scope = root.find("scope")
    assert scope is not None
    assert scope.text is not None
    assert "\\" not in scope.text
    assert "C:/Users/jon/AppData/Local/Temp/bugteam-pr-376/worktree" in scope.text


def test_bug_categories_carry_ids_a_through_p_in_order() -> None:
    root = _build_audit_root()
    bug_categories = root.find("bug_categories")
    assert bug_categories is not None
    all_emitted_ids = [each_category.get("id") for each_category in bug_categories]
    all_expected_ids = list("ABCDEFGHIJKLMNOP")
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


def test_prompt_skeleton_sub_bucket_counts_match_rubric_rows() -> None:
    """Each prompt skeleton's numeric sub-bucket count equals its rubric's row count.

    For every (letter, label) the prompts dir holds a category-<letter>- file.
    The skeleton above the first standalone --- line states "decomposed into N
    sub-buckets"; that N must equal the rubric's count of | <letter>N | rows,
    and a numeric walk-instruction range (For each sub-bucket X1-Xn) must end
    at that same row count. Skeletons with a [N] placeholder are skipped.
    """
    prompts_directory = _CATEGORY_RUBRICS_DIR.parent / "prompts"
    count_pattern = re.compile(r"decomposed into (\d+) sub-buckets")
    for each_letter, _each_label in ALL_AUDIT_CATEGORY_ENTRIES:
        all_prompt_matches = sorted(prompts_directory.glob(f"category-{each_letter.lower()}-*.md"))
        assert all_prompt_matches, f"Missing prompt file for category {each_letter}"
        all_skeleton_lines: list[str] = []
        for each_line in all_prompt_matches[0].read_text(encoding="utf-8").splitlines():
            if each_line == "---":
                break
            all_skeleton_lines.append(each_line)
        skeleton_text = "\n".join(all_skeleton_lines)
        each_count_match = count_pattern.search(skeleton_text)
        if each_count_match is None:
            assert "decomposed into [N] sub-buckets" in skeleton_text, (
                f"Category {each_letter}: skeleton neither states a numeric "
                "sub-bucket count nor carries the [N] placeholder"
            )
            continue
        all_rubric_matches = sorted(_CATEGORY_RUBRICS_DIR.glob(f"category-{each_letter.lower()}-*.md"))
        assert all_rubric_matches, f"Missing rubric file for category {each_letter}"
        rubric_row_pattern = re.compile(r"^\| " + each_letter + r"\d+ \|", re.MULTILINE)
        sub_bucket_row_count = len(rubric_row_pattern.findall(all_rubric_matches[0].read_text(encoding="utf-8")))
        assert int(each_count_match.group(1)) == sub_bucket_row_count, (
            f"Category {each_letter}: skeleton says {each_count_match.group(1)} sub-buckets "
            f"but rubric has {sub_bucket_row_count} rows"
        )
        walk_range_pattern = re.compile(
            rf"For each sub-bucket {each_letter}1[-–]{each_letter}(\d+)"
        )
        each_walk_match = walk_range_pattern.search(skeleton_text)
        if each_walk_match is not None:
            assert int(each_walk_match.group(1)) == sub_bucket_row_count, (
                f"Category {each_letter}: walk instruction ends at "
                f"{each_letter}{each_walk_match.group(1)} but rubric has "
                f"{sub_bucket_row_count} rows"
            )
