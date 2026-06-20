"""Tests for check_stale_test_name_target — Category N test-name-vs-scenario drift.

A test whose name embeds a function that has been renamed away — the body calls
the new same-shape name but the test identifier keeps the old one — advertises a
function that exists nowhere in the file. This is the deterministic slice of
Category N (test name vs scenario): the named target is a renamed-away sibling of
the function the body actually exercises.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_stale_test_name_target(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_stale_test_name_target(content, file_path)


TEST_FILE_PATH = "/project/scripts/test_scan_priority_queue.py"
PRODUCTION_FILE_PATH = "/project/scripts/scan_priority_queue.py"


def test_flags_renamed_away_target_in_test_name() -> None:
    content = (
        "from scan_priority_queue import collect_skip_clean_names\n"
        "\n\n"
        "def test_collect_skip_theme_names_keeps_only_sorted_at_risk() -> None:\n"
        "    all_skip_names = collect_skip_clean_names([])\n"
        "    assert all_skip_names == []\n"
    )
    issues = check_stale_test_name_target(content, TEST_FILE_PATH)
    assert len(issues) == 1
    assert "collect_skip_theme_names" in issues[0]
    assert "collect_skip_clean_names" in issues[0]


def test_flags_both_stale_names_in_renamed_producer_suite() -> None:
    content = (
        "from scan_priority_queue import collect_skip_clean_names\n"
        "\n\n"
        "def test_collect_skip_theme_names_keeps_only_sorted_at_risk() -> None:\n"
        "    assert collect_skip_clean_names([]) == []\n"
        "\n\n"
        "def test_collect_skip_theme_names_excludes_blank_names() -> None:\n"
        "    assert collect_skip_clean_names([]) == []\n"
    )
    issues = check_stale_test_name_target(content, TEST_FILE_PATH)
    assert len(issues) == 2


def test_passes_when_test_name_matches_called_function() -> None:
    content = (
        "from scan_priority_queue import collect_skip_clean_names\n"
        "\n\n"
        "def test_collect_skip_clean_names_keeps_only_sorted_at_risk() -> None:\n"
        "    assert collect_skip_clean_names([]) == []\n"
    )
    assert check_stale_test_name_target(content, TEST_FILE_PATH) == []


def test_ignores_ordinary_descriptive_test_name() -> None:
    content = (
        "from app import compute_total\n"
        "\n\n"
        "def test_compute_total_sums_line_items() -> None:\n"
        "    assert compute_total([1, 2]) == 3\n"
    )
    assert check_stale_test_name_target(content, TEST_FILE_PATH) == []


def test_ignores_neutral_behavior_test_name() -> None:
    content = (
        "from app import compute_total\n"
        "\n\n"
        "def test_returns_zero_on_empty_input() -> None:\n"
        "    assert compute_total([]) == 0\n"
    )
    assert check_stale_test_name_target(content, TEST_FILE_PATH) == []


def test_production_files_are_exempt() -> None:
    content = (
        "from scan_priority_queue import collect_skip_clean_names\n"
        "\n\n"
        "def test_collect_skip_theme_names_keeps_only_sorted_at_risk() -> None:\n"
        "    assert collect_skip_clean_names([]) == []\n"
    )
    assert check_stale_test_name_target(content, PRODUCTION_FILE_PATH) == []
