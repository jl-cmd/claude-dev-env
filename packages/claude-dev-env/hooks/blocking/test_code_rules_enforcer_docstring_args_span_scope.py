"""Span-scope tests for docstring checks.

Covers two surfaces:

1. ``check_docstring_args_single_line_scope_vs_span`` (Category O6) — an Args
   entry that claims single-line (block-anchor) scope while the body builds a
   multi-line span and routes it through span intersection.

2. Changed-span grading for ``check_docstring_runon_sentence`` and
   ``check_docstring_prose_wall_without_illustration`` (issue #237) — far-away
   no-op grandfathering, introduced-violation blocking, and
   ``defer_scope_to_caller`` pass-through.
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


def test_flags_single_line_scope_against_stepped_range_span_body() -> None:
    content = (
        "def check_import_block_sorted(\n"
        "    content: str, file_path: str, all_changed_lines: set[int] | None\n"
        ") -> list[str]:\n"
        '    """Flag an unsorted import block scoped to the changed lines.\n'
        "\n"
        "    Args:\n"
        "        content: The full file content the write would leave on disk.\n"
        "        file_path: The destination path used to gate by extension.\n"
        "        all_changed_lines: Post-edit line numbers, or None. When provided,\n"
        "            a finding blocks only when its block-anchor line is among the\n"
        "            changed lines.\n"
        "\n"
        "    Returns:\n"
        "        One issue string per detected finding.\n"
        '    """\n'
        "    span_range = range(line_number, block_end_line_number + 1, 1)\n"
        "    all_violations.append((span_range, message))\n"
        "    return _scope_violations_to_changed_lines(\n"
        "        all_violations, all_changed_lines, defer_scope_to_caller\n"
        "    )\n"
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

# ---------------------------------------------------------------------------
# Changed-span grading for the two whole-file docstring checks (issue #237 / P-41)
# check_docstring_runon_sentence and check_docstring_prose_wall_without_illustration
# ---------------------------------------------------------------------------


def check_docstring_runon_sentence(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    return code_rules_enforcer.check_docstring_runon_sentence(
        content, file_path, all_changed_lines, defer_scope_to_caller
    )


def check_docstring_prose_wall_without_illustration(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    return code_rules_enforcer.check_docstring_prose_wall_without_illustration(
        content, file_path, all_changed_lines, defer_scope_to_caller
    )


_CLEAN_HELPER_TAIL = (
    "\n"
    "def clean_helper() -> str:\n"
    '    """Return a short status token for the board.\n'
    "\n"
    "    Each call names one vessel and its final port.\n"
    '    """\n'
    '    return "ok"\n'
)


def _module_with_far_away_runon_and_clean_helper() -> str:
    return (
        '"""Owns the SIGINT install/restore/installability check, the atexit terminal-record\n'
        "registration, and the interrupted-run finalizer — the non-promoter-specific\n"
        "machinery that brackets a run so the JSONL artifact always carries a terminal\n"
        "record and an in-flight theme record on interrupt.\n"
        '"""\n'
        + _CLEAN_HELPER_TAIL
    )


def _module_with_far_away_prose_wall_and_clean_helper() -> str:
    return (
        '"""Assemble the nightly voyage tally from the harbor scans.\n'
        "\n"
        "A scan names one vessel and where it dropped anchor.\n"
        "The tally walks the scans in arrival order and keeps that order.\n"
        "A calm voyage ends well for every vessel it carried.\n"
        "A halted voyage marks the vessel it was near when the storm arrived.\n"
        "A wrecked voyage marks the vessel that sank and stops the walk there.\n"
        "The tally groups the vessels by their final port for the harbor.\n"
        "The harbor reads the tally and sees every arrival at a glance.\n"
        '"""\n'
        + _CLEAN_HELPER_TAIL
    )


def test_runon_far_away_no_op_is_grandfathered() -> None:
    content = _module_with_far_away_runon_and_clean_helper()
    clean_helper_line = content.splitlines().index("def clean_helper() -> str:") + 1
    all_changed_lines = set(range(clean_helper_line, clean_helper_line + 6))
    unscoped = check_docstring_runon_sentence(content, PRODUCTION_FILE_PATH)
    assert any("run-on" in each for each in unscoped), (
        f"control: unscoped must still see the far-away run-on, got {unscoped!r}"
    )
    scoped = check_docstring_runon_sentence(
        content, PRODUCTION_FILE_PATH, all_changed_lines=all_changed_lines
    )
    assert scoped == [], (
        f"far-away run-on must be grandfathered on a clean-helper edit, got {scoped!r}"
    )


def test_runon_introduced_violation_blocks() -> None:
    content = _module_with_far_away_runon_and_clean_helper()
    unscoped = check_docstring_runon_sentence(content, PRODUCTION_FILE_PATH)
    assert any("run-on" in each for each in unscoped)
    scoped = check_docstring_runon_sentence(
        content, PRODUCTION_FILE_PATH, all_changed_lines={1}
    )
    assert any("run-on" in each for each in scoped), (
        f"introduced/touched run-on must block, got {scoped!r}"
    )


def test_prose_wall_far_away_no_op_is_grandfathered() -> None:
    content = _module_with_far_away_prose_wall_and_clean_helper()
    clean_helper_line = content.splitlines().index("def clean_helper() -> str:") + 1
    all_changed_lines = set(range(clean_helper_line, clean_helper_line + 6))
    unscoped = check_docstring_prose_wall_without_illustration(
        content, PRODUCTION_FILE_PATH
    )
    assert any("worked example" in each for each in unscoped), (
        f"control: unscoped must still see the far-away wall, got {unscoped!r}"
    )
    scoped = check_docstring_prose_wall_without_illustration(
        content, PRODUCTION_FILE_PATH, all_changed_lines=all_changed_lines
    )
    assert scoped == [], (
        f"far-away wall must be grandfathered on a clean-helper edit, got {scoped!r}"
    )


def test_prose_wall_introduced_violation_blocks() -> None:
    content = _module_with_far_away_prose_wall_and_clean_helper()
    unscoped = check_docstring_prose_wall_without_illustration(
        content, PRODUCTION_FILE_PATH
    )
    assert any("worked example" in each for each in unscoped)
    scoped = check_docstring_prose_wall_without_illustration(
        content, PRODUCTION_FILE_PATH, all_changed_lines={1}
    )
    assert any("worked example" in each for each in scoped), (
        f"introduced/touched wall must block, got {scoped!r}"
    )


def test_runon_defer_scope_returns_all_violations() -> None:
    content = _module_with_far_away_runon_and_clean_helper()
    deferred = check_docstring_runon_sentence(
        content,
        PRODUCTION_FILE_PATH,
        all_changed_lines={999},
        defer_scope_to_caller=True,
    )
    assert any("run-on" in each for each in deferred)

