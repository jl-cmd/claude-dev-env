"""Tests for check_docstring_field_runmode_outcome — O6 run-mode-vs-per-record drift.

A dataclass field whose name marks a run-mode flag (``is_dry_run``) is documented
in the class Attributes block with per-record write-outcome prose ("True when no
STP was written"), while the value is set the same way for every record from the
run mode (``is_dry_run=not is_execute``). An already-OK record in an execute run
writes no file yet still stores ``False``, so the per-record prose misleads every
reader. This is the deterministic single-file slice of Category O6 drift.
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


def check_docstring_field_runmode_outcome(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_field_runmode_outcome(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/jsonl_writer.py"
TEST_FILE_PATH = "/project/src/test_jsonl_writer.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _drifted_record() -> str:
    return (
        "@dataclass(frozen=True)\n"
        "class PerThemeJsonlRecord:\n"
        '    """Exact schema for the per-theme JSONL line.\n'
        "\n"
        "    Attributes:\n"
        "        theme_name: Theme directory basename.\n"
        "        is_dry_run: True when no STP was written.\n"
        '    """\n'
        "\n"
        "    theme_name: str\n"
        "    is_dry_run: bool\n"
    )


def _run_mode_record() -> str:
    return (
        "@dataclass(frozen=True)\n"
        "class PerThemeJsonlRecord:\n"
        '    """Exact schema for the per-theme JSONL line.\n'
        "\n"
        "    Attributes:\n"
        "        theme_name: Theme directory basename.\n"
        "        is_dry_run: True for a dry run; False for an execute run.\n"
        '    """\n'
        "\n"
        "    theme_name: str\n"
        "    is_dry_run: bool\n"
    )


def test_flags_run_mode_field_documented_as_per_record_write_outcome() -> None:
    issues = check_docstring_field_runmode_outcome(_drifted_record(), PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "is_dry_run" in issues[0]
    assert "run-mode" in issues[0]


def test_run_mode_phrasing_is_left_alone() -> None:
    issues = check_docstring_field_runmode_outcome(_run_mode_record(), PRODUCTION_FILE_PATH)
    assert issues == []


def test_multiline_description_continuation_still_flags() -> None:
    source = (
        "@dataclass\n"
        "class Record:\n"
        '    """Schema.\n'
        "\n"
        "    Attributes:\n"
        "        is_dry_run: True for the record when\n"
        "            no STP was written.\n"
        '    """\n'
        "\n"
        "    is_dry_run: bool\n"
    )
    issues = check_docstring_field_runmode_outcome(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1


def test_non_run_mode_field_with_write_outcome_is_left_alone() -> None:
    source = (
        "@dataclass\n"
        "class Record:\n"
        '    """Schema.\n'
        "\n"
        "    Attributes:\n"
        "        stp_path: Path the STP was written to disk.\n"
        '    """\n'
        "\n"
        "    stp_path: str\n"
    )
    issues = check_docstring_field_runmode_outcome(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_test_file_is_exempt() -> None:
    issues = check_docstring_field_runmode_outcome(_drifted_record(), TEST_FILE_PATH)
    assert issues == []


def test_hook_infrastructure_is_exempt() -> None:
    issues = check_docstring_field_runmode_outcome(_drifted_record(), HOOK_INFRASTRUCTURE_PATH)
    assert issues == []


def test_syntax_error_returns_no_issues() -> None:
    issues = check_docstring_field_runmode_outcome("class Record(\n", PRODUCTION_FILE_PATH)
    assert issues == []
