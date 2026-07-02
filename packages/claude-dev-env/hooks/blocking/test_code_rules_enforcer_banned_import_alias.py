"""Unit tests for banned-identifier coverage of import aliases.

Covers the gap surfaced during PR #419: ``from config import rebase_constants as rc``
slipped past both the Write/Edit hook and the commit-time gate because the
banned-identifier check inspected only assignment targets, never import-alias
binding targets. Also covers the expanded abbreviation list (rc, cfg, ctx,
cnt, btn, idx, tmp, msg, elem, val) added per CODE_RULES.md §5.
"""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code_rules_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
check_banned_identifiers = hook_module.check_banned_identifiers

PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/services/test_loader.py"


def test_should_flag_from_import_alias_rc() -> None:
    content = "from config import rebase_constants as rc\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'rc'" in each_issue for each_issue in issues), (
        f"Expected 'rc' import alias flagged, got: {issues}"
    )


def test_should_flag_import_alias_rc() -> None:
    content = "import rebase_constants as rc\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'rc'" in each_issue for each_issue in issues), (
        f"Expected 'rc' bare-import alias flagged, got: {issues}"
    )


def test_should_flag_from_import_alias_cfg() -> None:
    content = "from app import configuration as cfg\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'cfg'" in each_issue for each_issue in issues), (
        f"Expected 'cfg' import alias flagged, got: {issues}"
    )


def test_should_flag_from_import_alias_ctx() -> None:
    content = "from app import context as ctx\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'ctx'" in each_issue for each_issue in issues), (
        f"Expected 'ctx' import alias flagged, got: {issues}"
    )


def test_should_flag_idx_assignment() -> None:
    content = "def pick(items):\n    idx = 0\n    return items[idx]\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'idx'" in each_issue for each_issue in issues), (
        f"Expected 'idx' assignment flagged — use index, got: {issues}"
    )


def test_should_flag_tmp_assignment() -> None:
    content = "def swap(a, b):\n    tmp = a\n    return tmp\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'tmp'" in each_issue for each_issue in issues), (
        f"Expected 'tmp' assignment flagged — use temporary_value, got: {issues}"
    )


def test_should_flag_msg_assignment() -> None:
    content = "def notify():\n    msg = build_message()\n    return msg\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'msg'" in each_issue for each_issue in issues), (
        f"Expected 'msg' assignment flagged — use message, got: {issues}"
    )


def test_should_flag_elem_assignment() -> None:
    content = "def first(items):\n    elem = items[0]\n    return elem\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'elem'" in each_issue for each_issue in issues), (
        f"Expected 'elem' assignment flagged — use element, got: {issues}"
    )


def test_should_flag_val_assignment() -> None:
    content = "def read():\n    val = compute()\n    return val\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'val'" in each_issue for each_issue in issues), (
        f"Expected 'val' assignment flagged — use value, got: {issues}"
    )


def test_should_flag_cnt_assignment() -> None:
    content = "def tally(items):\n    cnt = len(items)\n    return cnt\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'cnt'" in each_issue for each_issue in issues), (
        f"Expected 'cnt' assignment flagged — use count, got: {issues}"
    )


def test_should_flag_btn_assignment() -> None:
    content = "def click_handler():\n    btn = locate_button()\n    return btn\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'btn'" in each_issue for each_issue in issues), (
        f"Expected 'btn' assignment flagged — use button, got: {issues}"
    )


def test_should_scope_import_alias_in_test_file_to_changed_lines() -> None:
    content = "from config import rebase_constants as rc\n"
    unchanged_only = check_banned_identifiers(content, TEST_FILE_PATH, {2})
    assert unchanged_only == [], (
        f"A banned alias on an untouched line must not block, got: {unchanged_only}"
    )
    on_changed_line = check_banned_identifiers(content, TEST_FILE_PATH, {1})
    assert any("'rc'" in each_issue for each_issue in on_changed_line), (
        f"A newly written banned alias in a test file must flag, got: {on_changed_line}"
    )


def test_should_not_flag_import_alias_with_descriptive_name() -> None:
    content = (
        "from config import rebase_constants\n"
        "import json as json_module\n"
        "from typing import Optional as OptionalType\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"Descriptive import aliases must not flag, got: {issues}"


def test_should_include_line_number_for_import_alias() -> None:
    content = "import json\nfrom config import rebase_constants as rc\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert len(issues) >= 1
    assert "Line 2" in issues[0]
    assert "'rc'" in issues[0]
