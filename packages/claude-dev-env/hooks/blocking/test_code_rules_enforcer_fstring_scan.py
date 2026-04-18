"""Unit tests for code_rules_enforcer f-string structural literal scanner."""

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
check_fstring_structural_literals = hook_module.check_fstring_structural_literals
validate_content = hook_module.validate_content

PRODUCTION_FILE_PATH = "packages/claude-dev-env/example.py"
TEST_FILE_PATH = "packages/claude-dev-env/test_example.py"


def test_should_flag_fstring_with_url_path() -> None:
    content = 'def build_url(user_id):\n    endpoint = f"/api/v1/users/{user_id}"\n    return endpoint\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues, "expected URL path f-string to be flagged"


def test_should_flag_fstring_with_windows_path() -> None:
    content = 'def build_path(name):\n    location = f"C:\\\\Users\\\\{name}\\\\Documents"\n    return location\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues, "expected Windows path f-string to be flagged"


def test_should_flag_fstring_with_regex_pattern() -> None:
    content = 'def build_pattern(group):\n    regex = f"\\\\d+{group}\\\\w+"\n    return regex\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues, "expected regex metacharacter f-string to be flagged"


def test_should_not_flag_fstring_with_only_interpolation() -> None:
    content = 'def render(value):\n    rendered = f"{value}"\n    return rendered\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"pure interpolation should not be flagged, got: {issues}"


def test_should_not_flag_fstring_with_trivial_separator() -> None:
    content = 'def render(x):\n    rendered = f"{x} "\n    return rendered\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"single-space separator should not be flagged, got: {issues}"


def test_should_not_flag_true_false_literals() -> None:
    content = "def toggle():\n    x = True\n    y = False\n    return x, y\n"
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"True/False literals should not be flagged, got: {issues}"


def test_should_not_flag_empty_string_literal() -> None:
    content = 'def blank():\n    x = ""\n    return x\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"empty string literal should not be flagged, got: {issues}"


def test_should_skip_test_files() -> None:
    content = 'def test_thing():\n    url = f"/api/v1/users/{user_id}"\n'
    issues_via_validate = validate_content(content, TEST_FILE_PATH, "")
    fstring_issues = [
        each_issue
        for each_issue in issues_via_validate
        if "structural" in each_issue.lower() or "f-string" in each_issue.lower()
    ]
    assert fstring_issues == [], (
        f"test files should be exempt from f-string scanner, got: {fstring_issues}"
    )


def test_should_not_flag_natural_english_with_single_slash() -> None:
    content = 'def log_mode(mode):\n    message = f"Test name contains online/offline - mode is {mode}"\n    return message\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"natural English with single slash should not be flagged, got: {issues}"
    )


def test_should_not_flag_common_english_slash_phrases() -> None:
    for each_phrase in ("and/or", "CI/CD", "PR/MR", "input/output", "read/write"):
        content = f'def note(x):\n    message = f"{each_phrase} value is {{x}}"\n    return message\n'
        issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
        assert issues == [], (
            f"phrase {each_phrase!r} should not be flagged, got: {issues}"
        )


def test_should_flag_fstring_with_apostrophe() -> None:
    content = 'def greet(name):\n    message = f"it\'s /api/v1/{name}/home"\n    return message\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues, "f-string containing an apostrophe should still be detected"


def test_should_flag_triple_quoted_fstring_with_path() -> None:
    content = 'def build(x):\n    message = f"""/api/v1/{x}/path/extra"""\n    return message\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues, "triple-quoted f-string with path should be flagged"


def test_should_flag_raw_fstring_rf_prefix() -> None:
    content = 'def build(x):\n    message = rf"/api/v1/{x}/extra"\n    return message\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues, "rf-prefixed f-string with path should be flagged"


def test_should_flag_raw_fstring_fr_prefix() -> None:
    content = 'def build(x):\n    message = fr"/api/v1/{x}/extra"\n    return message\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    assert issues, "fr-prefixed f-string with path should be flagged"


def test_should_not_leak_escaped_braces_into_flag_message() -> None:
    content = 'def build(x):\n    message = f"{{/api/{x}/extra/path}}"\n    return message\n'
    issues = check_fstring_structural_literals(content, PRODUCTION_FILE_PATH)
    for each_issue in issues:
        assert "{{" not in each_issue, (
            f"flag message should not contain escaped brace artifacts, got: {each_issue}"
        )
        assert "}}" not in each_issue, (
            f"flag message should not contain escaped brace artifacts, got: {each_issue}"
        )


def test_should_not_flag_enforcer_hook_itself() -> None:
    hook_path = _HOOK_DIR / "code_rules_enforcer.py"
    with open(hook_path, encoding="utf-8") as each_file:
        enforcer_source = each_file.read()
    issues = check_fstring_structural_literals(
        enforcer_source,
        "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py",
    )
    assert issues == [], (
        f"the enforcer hook should not flag itself, got: {issues}"
    )
