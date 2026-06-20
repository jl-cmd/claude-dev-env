"""Tests for check_docstring_no_consumer_claim — Category O8 producer/consumer drift.

A producer docstring claiming "no consumer reads it yet" or "producer-only
artifact" is a transitional statement that drifts the moment a reader lands and
contradicts any companion SKILL.md that documents the consumer. This is the
deterministic slice of Category O8 (docstring / companion-doc producer-consumer
drift) and a no-transitional-language violation in its own right.
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


def check_docstring_no_consumer_claim(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_no_consumer_claim(content, file_path)


PRODUCTION_FILE_PATH = "/project/scripts/scan_priority_queue.py"
TEST_FILE_PATH = "/project/scripts/test_scan_priority_queue.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_flags_producer_only_artifact_claim() -> None:
    content = (
        "def write_skip_list(skip_list_path: str) -> int:\n"
        '    """Merge the at-risk names into the skip-list JSON.\n'
        "\n"
        "    This is a producer-only artifact; no submission-run consumer reads it yet.\n"
        "\n"
        "    Returns:\n"
        "        How many names the merged list holds.\n"
        '    """\n'
        "    return 0\n"
    )
    issues = check_docstring_no_consumer_claim(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "write_skip_list" in issues[0]


def test_flags_no_submission_run_consumer_phrase() -> None:
    content = (
        "def write_skip_list(skip_list_path: str) -> int:\n"
        '    """Write the JSON. No submission-run consumer reads it yet."""\n'
        "    return 0\n"
    )
    assert len(check_docstring_no_consumer_claim(content, PRODUCTION_FILE_PATH)) == 1


def test_passes_when_docstring_names_the_consumer() -> None:
    content = (
        "def write_skip_list(skip_list_path: str) -> int:\n"
        '    """Write the JSON. The new-theme submission run reads it and applies the skip.\n'
        "\n"
        "    Returns:\n"
        "        How many names the merged list holds.\n"
        '    """\n'
        "    return 0\n"
    )
    assert check_docstring_no_consumer_claim(content, PRODUCTION_FILE_PATH) == []


def test_test_files_are_exempt() -> None:
    content = (
        "def write_skip_list(skip_list_path: str) -> int:\n"
        '    """This is a producer-only artifact; no consumer reads it yet."""\n'
        "    return 0\n"
    )
    assert check_docstring_no_consumer_claim(content, TEST_FILE_PATH) == []


def test_hook_infrastructure_is_exempt() -> None:
    content = (
        "def write_skip_list(skip_list_path: str) -> int:\n"
        '    """This is a producer-only artifact; no consumer reads it yet."""\n'
        "    return 0\n"
    )
    assert check_docstring_no_consumer_claim(content, HOOK_INFRASTRUCTURE_PATH) == []
