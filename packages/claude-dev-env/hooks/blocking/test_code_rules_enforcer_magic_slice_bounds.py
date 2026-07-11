"""Tests for slice-bound magic values in the magic-value check.

CODE_RULES.md states only 0, 1, -1 (plus 0.0, 1.0) are exempt from the
magic-value check. A magic number used as a slice bound (``sha[:8]``,
``timestamp[:10]``) is still a magic value, while a plain subscript index
(``items[2]``) rides on the bracket exemption. The check distinguishes the
two by the colon a slice carries between its brackets.
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


PRODUCTION_FILE_PATH = "packages/claude-dev-env/skills/example/workflow/example_render.py"


def test_check_magic_values_should_flag_short_sha_slice_bound() -> None:
    source = (
        "def render_fix(fix_record):\n"
        "    short_sha = fix_record.new_sha[:8]\n"
        "    label = short_sha\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(issue.endswith("Magic value 8 - extract to named constant") for issue in issues), (
        f"Expected magic-value issue for slice bound 8, got: {issues}"
    )


def test_check_magic_values_should_flag_iso_date_prefix_slice_bound() -> None:
    source = (
        "def read_date(journal):\n"
        "    timestamp = journal.get_timestamp()\n"
        "    generated = timestamp[:10]\n"
        "    label = generated\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(issue.endswith("Magic value 10 - extract to named constant") for issue in issues), (
        f"Expected magic-value issue for slice bound 10, got: {issues}"
    )


def test_check_magic_values_should_flag_slice_bound_even_with_inline_guard() -> None:
    source = (
        "def read_date(journal):\n"
        "    timestamp = journal.get_timestamp()\n"
        '    generated = timestamp[:10] if len(timestamp) >= 10 else ""\n'
        "    label = generated\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(issue.endswith("Magic value 10 - extract to named constant") for issue in issues), (
        f"Expected magic-value issue for slice bound 10 on a guarded line, got: {issues}"
    )


def test_check_magic_values_should_still_exempt_plain_subscript_index() -> None:
    source = "def pick_entry(all_entries):\n    chosen = all_entries[2]\n    label = chosen\n"
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for a plain subscript index, got: {issues}"


def test_check_magic_values_should_allow_slice_bound_of_one() -> None:
    source = "def first_character(text):\n    head = text[:1]\n    label = head\n"
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for an allowed slice bound 1, got: {issues}"


def test_check_magic_values_should_flag_slice_bound_not_substring_subscript_on_same_line() -> None:
    source = (
        "def join_pair(key, value):\n"
        "    pair = key[2] + value[:20]\n"
        "    label = pair\n"
    )
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(issue.endswith("Magic value 20 - extract to named constant") for issue in issues), (
        f"Expected the slice bound 20 to be flagged, got: {issues}"
    )
    assert not any(issue.endswith("Magic value 2 - extract to named constant") for issue in issues), (
        f"Expected the subscript index 2 to stay exempt, got: {issues}"
    )


def test_check_magic_values_should_flag_first_token_of_two_sided_slice() -> None:
    source = "def middle(chunk):\n    window = chunk[8:16]\n    label = window\n"
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(issue.endswith("Magic value 8 - extract to named constant") for issue in issues), (
        f"Expected the first slice bound 8 to be flagged, got: {issues}"
    )


def test_check_magic_values_should_exempt_walrus_subscript_index() -> None:
    source = "def lookup(all_entries):\n    chosen = all_entries[(n := 4)]\n    label = chosen\n"
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for a walrus subscript index, got: {issues}"


def test_check_magic_values_should_exempt_lambda_subscript_index() -> None:
    source = "def lookup(sequence):\n    chosen = sequence[(lambda: 7)()]\n    label = chosen\n"
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Expected no issues for a lambda subscript index, got: {issues}"


def test_check_magic_values_should_flag_outer_slice_bound_not_inner_subscript() -> None:
    source = "def window(first, second):\n    region = first[second[6]:9]\n    label = region\n"
    issues = code_rules_enforcer.check_magic_values(source, PRODUCTION_FILE_PATH)
    assert any(issue.endswith("Magic value 9 - extract to named constant") for issue in issues), (
        f"Expected the outer slice bound 9 to be flagged, got: {issues}"
    )
    assert not any(issue.endswith("Magic value 6 - extract to named constant") for issue in issues), (
        f"Expected the inner subscript index 6 to stay exempt, got: {issues}"
    )


def test_check_magic_values_should_pass_on_the_module_own_source() -> None:
    module_path = Path(__file__).parent / "code_rules_magic_values.py"
    source = module_path.read_text(encoding="utf-8")
    issues = code_rules_enforcer.check_magic_values(source, str(module_path))
    assert issues == [], f"Expected the module to pass its own magic-value check, got: {issues}"
