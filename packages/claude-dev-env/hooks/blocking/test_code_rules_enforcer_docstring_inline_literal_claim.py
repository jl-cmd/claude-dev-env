"""Tests for check_docstring_no_inline_literal_claim — Category O6 completeness drift.

A constants-module docstring asserting "no literals appear inline in the
dispatcher" makes an unverifiable completeness claim about a companion file. The
claim drifts the moment a literal lands inline in that companion — a deny or
block reason left inline contradicts the docstring even though the file under
edit never changed. This is the deterministic slice of Category O6 (docstring
prose vs implementation drift) and a no-transitional-language violation in its
own right.
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


def check_docstring_no_inline_literal_claim(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_no_inline_literal_claim(content, file_path)


CONSTANTS_FILE_PATH = "/project/hooks/hooks_constants/example_dispatcher_constants.py"
TEST_FILE_PATH = "/project/hooks/hooks_constants/test_example_dispatcher_constants.py"


def test_flags_no_literals_appear_inline_in_the_dispatcher_claim() -> None:
    content = (
        '"""Constants for the dispatcher.\n'
        "\n"
        "The dispatcher imports these; no literals appear inline in the dispatcher\n"
        "script.\n"
        '"""\n'
        "\n"
        'DENY_DECISION = "deny"\n'
    )
    issues = check_docstring_no_inline_literal_claim(content, CONSTANTS_FILE_PATH)
    assert len(issues) == 1
    assert "no literals appear inline" in issues[0]


def test_flags_no_literals_appear_inline_short_form() -> None:
    content = (
        '"""Constants module. No literals appear inline in the script."""\n'
        "\n"
        'BLOCK_DECISION = "block"\n'
    )
    assert len(check_docstring_no_inline_literal_claim(content, CONSTANTS_FILE_PATH)) == 1


def test_passes_when_docstring_states_what_is_centralized() -> None:
    content = (
        '"""Constants for the dispatcher.\n'
        "\n"
        "Holds the deny decision string and the crash deny reason. The dispatcher\n"
        "imports each of these by name.\n"
        '"""\n'
        "\n"
        'DENY_DECISION = "deny"\n'
    )
    assert check_docstring_no_inline_literal_claim(content, CONSTANTS_FILE_PATH) == []


def test_test_files_are_exempt() -> None:
    content = (
        '"""Constants module. No literals appear inline in the dispatcher script."""\n'
        "\n"
        'DENY_DECISION = "deny"\n'
    )
    assert check_docstring_no_inline_literal_claim(content, TEST_FILE_PATH) == []


def test_hook_infrastructure_is_in_scope() -> None:
    hook_constants_path = "/home/user/.claude/hooks/hooks_constants/foo_constants.py"
    content = (
        '"""Constants module. No literals appear inline in the dispatcher script."""\n'
        "\n"
        'DENY_DECISION = "deny"\n'
    )
    assert len(check_docstring_no_inline_literal_claim(content, hook_constants_path)) == 1
