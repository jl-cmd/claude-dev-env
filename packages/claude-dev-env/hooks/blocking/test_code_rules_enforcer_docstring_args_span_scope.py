"""Tests for check_docstring_args_single_line_scope_vs_span — Category O6 drift.

A docstring Args: entry that scopes a finding to one named line ("only when its
block-anchor line is among the changed lines") while the body builds a range()
span and routes it through a span-intersection scoper claims a narrower scope
than the code applies. The body blocks when ANY line of the span is among the
changed lines, so an edit touching a non-anchor line of the span still blocks —
contradicting the single-line Args sentence. This is the deterministic slice of
Category O6 (free-form docstring-vs-implementation drift) for an Args entry whose
single-line scope claim disagrees with a span-intersection body.
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


def check_docstring_args_single_line_scope_vs_span(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_args_single_line_scope_vs_span(content, file_path)


PRODUCTION_FILE_PATH = "/project/scripts/check_import_block_sorted.py"
TEST_FILE_PATH = "/project/scripts/test_check_import_block_sorted.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


SPAN_SCOPING_BODY = (
    "    span_range = range(line_number, block_end_line_number + 1)\n"
    "    all_violations.append((span_range, message))\n"
    "    return _scope_violations_to_changed_lines(\n"
    "        all_violations, all_changed_lines, defer_scope_to_caller\n"
    "    )\n"
)


def test_flags_anchor_line_scope_against_span_intersection_body() -> None:
    content = (
        "def check_import_block_sorted(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag an unsorted import block scoped to the changed lines.\n'
        "\n"
        "    A finding is returned when any line in that block span is among\n"
        "    all_changed_lines.\n"
        "\n"
        "    Args:\n"
        "        content: The full file content the write would leave on disk.\n"
        "        file_path: The destination path used to gate by extension.\n"
        "        all_changed_lines: Post-edit line numbers the current edit touched, or\n"
        "            None to treat the whole file as in scope. When provided, a finding\n"
        "            blocks only when its block-anchor line is among the changed lines.\n"
        "\n"
        "    Returns:\n"
        "        One issue string per detected finding.\n"
        '    """\n' + SPAN_SCOPING_BODY
    )
    issues = check_docstring_args_single_line_scope_vs_span(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "check_import_block_sorted" in issues[0]
    assert "all_changed_lines" in issues[0]


def test_flags_the_line_is_among_phrasing() -> None:
    content = (
        "def check_block(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag an unsorted block scoped to the diff.\n'
        "\n"
        "    Args:\n"
        "        content: The file content.\n"
        "        all_changed_lines: When provided, a finding blocks only when the\n"
        "            anchor line is among the changed lines.\n"
        '    """\n' + SPAN_SCOPING_BODY
    )
    assert len(check_docstring_args_single_line_scope_vs_span(content, PRODUCTION_FILE_PATH)) == 1


def test_passes_when_args_says_any_line_of_the_span() -> None:
    content = (
        "def check_import_block_sorted(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag an unsorted import block scoped to the changed lines.\n'
        "\n"
        "    Args:\n"
        "        content: The full file content.\n"
        "        all_changed_lines: Post-edit line numbers the current edit touched, or\n"
        "            None to treat the whole file as in scope. When provided, a finding\n"
        "            blocks only when any line of its block span is among the changed lines.\n"
        '    """\n' + SPAN_SCOPING_BODY
    )
    assert check_docstring_args_single_line_scope_vs_span(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_body_scopes_by_single_line_not_a_span() -> None:
    content = (
        "def check_one_line(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag a violation on a single line scoped to the diff.\n'
        "\n"
        "    Args:\n"
        "        content: The file content.\n"
        "        all_changed_lines: When provided, a finding blocks only when its\n"
        "            anchor line is among the changed lines.\n"
        '    """\n'
        "    if all_changed_lines is not None and line_number not in all_changed_lines:\n"
        "        return []\n"
        "    return [message]\n"
    )
    assert check_docstring_args_single_line_scope_vs_span(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_no_single_line_scope_phrase() -> None:
    content = (
        "def check_import_block_sorted(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag an unsorted import block scoped to the changed lines.\n'
        "\n"
        "    Args:\n"
        "        content: The full file content.\n"
        "        all_changed_lines: Post-edit line numbers the current edit touched.\n"
        '    """\n' + SPAN_SCOPING_BODY
    )
    assert check_docstring_args_single_line_scope_vs_span(content, PRODUCTION_FILE_PATH) == []


def test_test_files_are_exempt() -> None:
    content = (
        "def check_import_block_sorted(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag an unsorted import block.\n'
        "\n"
        "    Args:\n"
        "        all_changed_lines: A finding blocks only when its anchor line is\n"
        "            among the changed lines.\n"
        '    """\n' + SPAN_SCOPING_BODY
    )
    assert check_docstring_args_single_line_scope_vs_span(content, TEST_FILE_PATH) == []


def test_hook_infrastructure_is_not_exempt() -> None:
    content = (
        "def check_import_block_sorted(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag an unsorted import block.\n'
        "\n"
        "    Args:\n"
        "        all_changed_lines: A finding blocks only when its block-anchor line is\n"
        "            among the changed lines.\n"
        '    """\n' + SPAN_SCOPING_BODY
    )
    assert (
        len(check_docstring_args_single_line_scope_vs_span(content, HOOK_INFRASTRUCTURE_PATH)) == 1
    )
