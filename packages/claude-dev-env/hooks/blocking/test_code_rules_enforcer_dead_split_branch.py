from __future__ import annotations

import importlib.util
from pathlib import Path

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
assert specification is not None and specification.loader is not None
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_PATH = "C:/project/pkg/menu_info_colors.py"


def _check(source: str) -> list[str]:
    return code_rules_enforcer.check_dead_split_truthiness_branch(source, PRODUCTION_PATH)


def test_flags_split_truthiness_else_arm() -> None:
    source = (
        "def _extract_uid_prefix(uid: str) -> str:\n"
        '    all_parts = uid.split("_")\n'
        "    if len(all_parts) > 2:\n"
        '        return "_".join(all_parts[:3])\n'
        "    return all_parts[0] if all_parts else uid\n"
    )
    issues = _check(source)
    assert len(issues) == 1
    assert "all_parts" in issues[0]
    assert "Line 5" in issues[0]


def test_flags_negated_guard_dead_body() -> None:
    source = (
        "def first_segment(path: str) -> str:\n"
        '    all_segments = path.split("/")\n'
        "    if not all_segments:\n"
        "        return path\n"
        "    return all_segments[0]\n"
    )
    issues = _check(source)
    assert len(issues) == 1
    assert "all_segments" in issues[0]


def test_does_not_flag_split_without_separator() -> None:
    source = (
        "def first_token(text: str) -> str:\n"
        "    all_parts = text.split()\n"
        "    return all_parts[0] if all_parts else text\n"
    )
    assert _check(source) == []


def test_does_not_flag_length_comparison_guard() -> None:
    source = (
        "def prefix(uid: str) -> str:\n"
        '    all_parts = uid.split("_")\n'
        "    if len(all_parts) > 1:\n"
        "        return all_parts[0]\n"
        "    return uid\n"
    )
    assert _check(source) == []


def test_does_not_flag_when_name_reassigned() -> None:
    source = (
        "def normalize(uid: str) -> str:\n"
        '    all_parts = uid.split("_")\n'
        "    all_parts = [each_part.strip() for each_part in all_parts]\n"
        "    return all_parts[0] if all_parts else uid\n"
    )
    assert _check(source) == []


def test_does_not_flag_when_name_is_parameter() -> None:
    source = (
        "def shape(all_parts: list[str]) -> str:\n"
        '    all_parts = "x".split("_")\n'
        '    return all_parts[0] if all_parts else ""\n'
    )
    assert _check(source) == []


def test_does_not_flag_attribute_receiver_split() -> None:
    source = (
        "def first(s: object) -> object:\n"
        '    parts = s.str.split(",")\n'
        "    return parts[0] if parts else 0\n"
    )
    assert _check(source) == []


def test_does_not_flag_in_test_file() -> None:
    source = (
        "def helper(uid: str) -> str:\n"
        '    all_parts = uid.split("_")\n'
        "    return all_parts[0] if all_parts else uid\n"
    )
    assert (
        code_rules_enforcer.check_dead_split_truthiness_branch(
            source, "C:/project/pkg/test_thing.py"
        )
        == []
    )
