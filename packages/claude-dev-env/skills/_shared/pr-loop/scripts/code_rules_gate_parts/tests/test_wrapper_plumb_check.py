"""Behavioral tests for the wrapper_plumb_check parts module."""

from pathlib import Path

from code_rules_gate_parts import wrapper_plumb_check


def test_is_code_path_recognizes_python() -> None:
    assert wrapper_plumb_check.is_code_path(Path("module.py"))
    assert not wrapper_plumb_check.is_code_path(Path("notes.txt"))


def test_is_test_path_matches_the_documented_patterns() -> None:
    assert wrapper_plumb_check.is_test_path("pkg/test_bar.py")
    assert wrapper_plumb_check.is_test_path("pkg/bar_test.py")
    assert wrapper_plumb_check.is_test_path("pkg/conftest.py")
    assert wrapper_plumb_check.is_test_path("pkg/tests/thing.py")
    assert not wrapper_plumb_check.is_test_path("pkg/regular.py")


def test_check_wrapper_plumb_through_flags_dropped_kwarg() -> None:
    content = (
        "def build(name, verbose=False):\n"
        "    return name\n\n\n"
        "def wrap(name):\n"
        "    return build(name)\n"
    )
    findings = wrapper_plumb_check.check_wrapper_plumb_through(content, "module.py")
    assert any("verbose" in each_finding for each_finding in findings)


def test_check_wrapper_plumb_through_is_quiet_for_test_files() -> None:
    content = (
        "def build(name, verbose=False):\n"
        "    return name\n\n\n"
        "def wrap(name):\n"
        "    return build(name)\n"
    )
    assert wrapper_plumb_check.check_wrapper_plumb_through(content, "test_module.py") == []


def test_check_wrapper_plumb_through_is_quiet_when_kwarg_is_plumbed() -> None:
    content = (
        "def build(name, verbose=False):\n"
        "    return name\n\n\n"
        "def wrap(name, verbose=False):\n"
        "    return build(name, verbose=verbose)\n"
    )
    assert wrapper_plumb_check.check_wrapper_plumb_through(content, "module.py") == []
