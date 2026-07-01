"""Tests for check_docstring_names_absent_type_checking_gate — Category O6.

A module or function docstring that names a ``TYPE_CHECKING`` gate-detection step,
or a ``type-checking-gate`` helper family, drifts once no identifier in the body
handles TYPE_CHECKING: the prose points a reader at machinery the module does not
hold. This is the deterministic slice of Category O6 (docstring prose versus
implementation drift) for a TYPE_CHECKING gate claim. The check covers hook
infrastructure, where the import-scan gates that carry this drift class live.
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


def check_type_checking_gate(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_names_absent_type_checking_gate(content, file_path)


PRODUCTION_HOOK_PATH = "/home/user/.claude/hooks/blocking/code_rules_unused_imports.py"
TEST_FILE_PATH = "/home/user/.claude/hooks/blocking/test_code_rules_unused_imports.py"


def test_flags_module_docstring_naming_type_checking_gate_helpers() -> None:
    content = (
        '"""Unused module-level import check and its import-range and '
        'type-checking-gate helpers."""\n'
        "\n"
        "import ast\n"
        "\n"
        "\n"
        "def check_unused(content: str) -> list[str]:\n"
        '    """Flag unused imports."""\n'
        "    return []\n"
    )
    issues = check_type_checking_gate(content, PRODUCTION_HOOK_PATH)
    assert len(issues) == 1
    assert issues[0].startswith("Line 1:")
    assert "type-checking-gate" in issues[0]


def test_flags_function_docstring_naming_type_checking_gate_detection() -> None:
    content = (
        "import ast\n"
        "\n"
        "\n"
        "def check_unused_module_level_imports(content: str) -> list[str]:\n"
        '    """Flag module-level imports never referenced.\n'
        "\n"
        "    When ``full_file_content`` is provided, the ``__all__`` /\n"
        "    ``TYPE_CHECKING`` gate detection and reference scanning run against\n"
        "    ``full_file_content``.\n"
        '    """\n'
        "    return []\n"
    )
    issues = check_type_checking_gate(content, PRODUCTION_HOOK_PATH)
    assert len(issues) == 1
    assert "type_checking gate" in issues[0]


def test_flags_both_module_and_function_docstrings_on_the_real_drift() -> None:
    content = (
        '"""Unused module-level import check and its import-range and '
        'type-checking-gate helpers."""\n'
        "\n"
        "import ast\n"
        "\n"
        "\n"
        "def check_unused_module_level_imports(content: str) -> list[str]:\n"
        '    """Flag module-level imports never referenced.\n'
        "\n"
        "    The ``__all__`` / ``TYPE_CHECKING`` gate detection and reference\n"
        "    scanning run against ``full_file_content``.\n"
        '    """\n'
        "    return []\n"
    )
    issues = check_type_checking_gate(content, PRODUCTION_HOOK_PATH)
    assert len(issues) == 2


def test_passes_when_code_declares_a_type_checking_gate_helper() -> None:
    content = (
        '"""Unused module-level import check and its type-checking-gate helpers."""\n'
        "\n"
        "import ast\n"
        "\n"
        "\n"
        "def _module_body_declares_type_checking_gate(tree: ast.Module) -> bool:\n"
        '    """Return True when the module guards imports behind TYPE_CHECKING."""\n'
        "    return False\n"
    )
    assert check_type_checking_gate(content, PRODUCTION_HOOK_PATH) == []


def test_passes_when_body_names_type_checking_guard() -> None:
    content = (
        "import ast\n"
        "from typing import TYPE_CHECKING\n"
        "\n"
        "\n"
        "def check_unused(content: str) -> list[str]:\n"
        '    """Skip imports the ``TYPE_CHECKING`` gate detection guards."""\n'
        "    if TYPE_CHECKING:\n"
        "        return []\n"
        "    return []\n"
    )
    assert check_type_checking_gate(content, PRODUCTION_HOOK_PATH) == []


def test_passes_when_no_docstring_names_the_gate() -> None:
    content = (
        '"""Unused module-level import check and its import-range helpers."""\n'
        "\n"
        "import ast\n"
        "\n"
        "\n"
        "def check_unused(content: str) -> list[str]:\n"
        '    """Flag module-level imports never referenced."""\n'
        "    return []\n"
    )
    assert check_type_checking_gate(content, PRODUCTION_HOOK_PATH) == []


def test_test_files_are_exempt() -> None:
    content = (
        '"""Unused module-level import check and its type-checking-gate helpers."""\n'
        "\n"
        "import ast\n"
        "\n"
        "\n"
        "def check_unused(content: str) -> list[str]:\n"
        '    """Flag unused imports."""\n'
        "    return []\n"
    )
    assert check_type_checking_gate(content, TEST_FILE_PATH) == []
