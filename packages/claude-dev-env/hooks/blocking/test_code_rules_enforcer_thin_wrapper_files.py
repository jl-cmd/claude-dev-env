"""Tests for check_thin_wrapper_files — flag re-export-only modules.

Per Plan / Phase B5: a non-`__init__.py` module whose entire body is
`import` statements plus an `__all__` assignment is a thin wrapper that
forces callers through an indirection layer with no payload. Callers
should import from the real module. `__init__.py` is the canonical
re-export surface and is exempt.
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


def check_thin_wrapper_files(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_thin_wrapper_files(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/aliases.py"
INIT_FILE_PATH = "/project/src/__init__.py"
TEST_FILE_PATH = "/project/src/test_aliases.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"
CONFIG_FILE_PATH = "/project/config/aliases.py"


def test_should_flag_thin_wrapper_with_imports_and_all() -> None:
    source = (
        "from real_module import do_thing, other_thing\n"
        "\n"
        '__all__ = ["do_thing", "other_thing"]\n'
    )
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert any("thin wrapper" in each.lower() for each in issues), (
        f"Expected thin-wrapper flag, got: {issues!r}"
    )


def test_should_flag_thin_wrapper_imports_only_no_all() -> None:
    source = "from real_module import do_thing\nfrom other_module import other_thing\n"
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert any("thin wrapper" in each.lower() for each in issues), (
        f"Expected import-only thin-wrapper flag, got: {issues!r}"
    )


def test_should_not_flag_init_file() -> None:
    source = 'from real_module import do_thing\n\n__all__ = ["do_thing"]\n'
    issues = check_thin_wrapper_files(source, INIT_FILE_PATH)
    assert issues == [], (
        f"__init__.py is the canonical re-export surface, got: {issues!r}"
    )


def test_should_not_flag_file_with_function_definition() -> None:
    source = (
        "from real_module import dependency\n"
        "\n"
        '__all__ = ["public_helper"]\n'
        "\n"
        "def public_helper(value: int) -> int:\n"
        "    return dependency(value)\n"
    )
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"File with real code must not be flagged, got: {issues!r}"


def test_should_not_flag_file_with_class_definition() -> None:
    source = "from real_module import Base\n\nclass Subtype(Base):\n    pass\n"
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"File with class must not be flagged, got: {issues!r}"


def test_should_not_flag_file_with_constant_assignment() -> None:
    source = (
        "from real_module import constant_value\n\nDERIVED_VALUE = constant_value * 2\n"
    )
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"File with derived constant must not be flagged, got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    source = "from real_module import do_thing\n\n__all__ = ['do_thing']\n"
    issues = check_thin_wrapper_files(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    source = "from real_module import do_thing\n\n__all__ = ['do_thing']\n"
    issues = check_thin_wrapper_files(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_skip_config_file() -> None:
    source = "from real_module import do_thing\n\n__all__ = ['do_thing']\n"
    issues = check_thin_wrapper_files(source, CONFIG_FILE_PATH)
    assert issues == [], f"config/ files exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    source = "from real_module import (\n"
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_should_not_flag_empty_file() -> None:
    issues = check_thin_wrapper_files("", PRODUCTION_FILE_PATH)
    assert issues == [], f"Empty file must not be flagged, got: {issues!r}"


def test_should_not_flag_module_docstring_with_real_code() -> None:
    source = (
        '"""Module docstring."""\n'
        "from real_module import dependency\n"
        "\n"
        "def helper() -> int:\n"
        "    return dependency()\n"
    )
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Docstring + real code must not be flagged, got: {issues!r}"


def test_should_flag_thin_wrapper_with_module_docstring() -> None:
    source = (
        '"""Module docstring."""\n'
        "from real_module import do_thing\n"
        "\n"
        '__all__ = ["do_thing"]\n'
    )
    issues = check_thin_wrapper_files(source, PRODUCTION_FILE_PATH)
    assert any("thin wrapper" in each.lower() for each in issues), (
        f"Docstring + import + __all__ is still a thin wrapper, got: {issues!r}"
    )


def test_validate_content_uses_empty_full_file_content_over_pre_edit_fragment() -> None:
    """An empty-string `full_file_content` must be honored, not silently replaced with `content`.

    Regression for loop1-8: the `or` short-circuit at line 3775 collapsed
    empty-string and None, so an Edit that produced an empty post-edit file
    was scanned against the pre-edit fragment instead of the empty file.
    The thin-wrapper check uses the same idiom — an empty post-edit file is
    not a thin wrapper, but a pre-edit fragment with imports + __all__ is.
    """
    pre_edit_fragment = "from real_module import do_thing\n__all__ = ['do_thing']\n"
    issues = code_rules_enforcer.validate_content(
        pre_edit_fragment,
        PRODUCTION_FILE_PATH,
        full_file_content="",
    )
    assert not any("thin wrapper" in each.lower() for each in issues), (
        f"empty post-edit file must not be flagged as a thin wrapper, got: {issues!r}"
    )
