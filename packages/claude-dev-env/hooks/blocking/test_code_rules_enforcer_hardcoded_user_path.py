"""Tests for hardcoded user path detection.

Bot reviewers on PR #257 flagged 6+ instances of 'C:/Users/jon/' embedded
in production source code, which breaks portability across machines.
The new rule flags any string literal in production code that names a
specific user's home directory.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys


_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code_rules_enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
check_hardcoded_user_paths = _hook_module.check_hardcoded_user_paths
HARDCODED_USER_PATH_PATTERN = _hook_module.HARDCODED_USER_PATH_PATTERN


PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/tests/test_loader.py"
CONFIG_FILE_PATH = "packages/app/config/paths.py"
HOOK_INFRASTRUCTURE_FILE_PATH = "/repo/packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py"


def test_should_match_user_directory_without_consuming_following_separator() -> None:
    windows = HARDCODED_USER_PATH_PATTERN.search("C:/Users/jon/more")
    macos = HARDCODED_USER_PATH_PATTERN.search("/Users/bob/more")
    linux = HARDCODED_USER_PATH_PATTERN.search("/home/alice/more")
    assert windows is not None and windows.group(0) == "C:/Users/jon"
    assert macos is not None and macos.group(0) == "/Users/bob"
    assert linux is not None and linux.group(0) == "/home/alice"


def test_should_flag_windows_user_path_with_forward_slashes() -> None:
    source = 'def find() -> str:\n    return "C:/Users/jon/notes.md"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("C:/Users/jon" in each_issue for each_issue in issues), (
        f"Expected Windows user path flagged, got: {issues}"
    )


def test_should_flag_windows_user_path_when_users_segment_is_not_title_case() -> None:
    source = 'def find() -> str:\n    return "c:/users/jon/notes.md"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("users" in each_issue.lower() for each_issue in issues), (
        f"Expected Windows user path flagged (case-insensitive Users segment), got: {issues}"
    )


def test_should_flag_windows_user_path_with_backslashes() -> None:
    source = 'def find() -> str:\n    return "C:\\\\Users\\\\jon\\\\notes.md"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("Users" in each_issue for each_issue in issues), (
        f"Expected Windows backslash user path flagged, got: {issues}"
    )


def test_should_flag_unix_home_path() -> None:
    source = 'def find() -> str:\n    return "/home/alice/notes.md"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("/home/alice" in each_issue for each_issue in issues), (
        f"Expected Unix home path flagged, got: {issues}"
    )


def test_should_flag_macos_user_path() -> None:
    source = 'def find() -> str:\n    return "/Users/bob/Documents/data.json"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("/Users/bob" in each_issue for each_issue in issues), (
        f"Expected macOS user path flagged, got: {issues}"
    )


def test_should_flag_macos_user_path_when_home_is_entire_path() -> None:
    source = 'def find() -> str:\n    return "/Users/bob"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("/Users/bob" in each_issue for each_issue in issues), (
        f"Expected macOS user home literal flagged without trailing slash, got: {issues}"
    )


def test_should_not_flag_tilde_home_alias() -> None:
    source = 'def find() -> str:\n    return "~/notes.md"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Tilde alias is portable, must not flag, got: {issues}"


def test_should_not_flag_users_directory_without_specific_user() -> None:
    source = 'def root_dir() -> str:\n    return "C:/Users"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Generic /Users root with no specific user has no portability cost, got: {issues}"
    )


def test_should_skip_test_files() -> None:
    source = 'def test_path() -> None:\n    fixture = "C:/Users/jon/scratch.txt"\n'
    issues = check_hardcoded_user_paths(source, TEST_FILE_PATH)
    assert issues == [], (
        f"Test files exempt — fixtures often need real paths, got: {issues}"
    )


def test_should_skip_config_files() -> None:
    source = 'DEFAULT_PATH = "C:/Users/jon/notes.md"\n'
    issues = check_hardcoded_user_paths(source, CONFIG_FILE_PATH)
    assert issues == [], (
        f"Config files exempt — that is the right place for paths, got: {issues}"
    )


def test_should_include_line_number_in_issue() -> None:
    source = '\n\ndef find() -> str:\n    return "C:/Users/jon/notes.md"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("Line 4" in each_issue for each_issue in issues), (
        f"Expected line 4 reference, got: {issues}"
    )


def test_should_handle_syntax_error_gracefully() -> None:
    source = "def broken(\n    not python\n"
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Parse failure must return empty, got: {issues}"


def test_should_suggest_path_home_or_expanduser_in_message() -> None:
    source = 'def find() -> str:\n    return "/home/alice/x"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any(
        "Path.home" in each_issue or "expanduser" in each_issue for each_issue in issues
    ), (
        f"Error message should suggest Path.home() or os.path.expanduser('~'), got: {issues}"
    )

def test_should_flag_standalone_home_segment_for_symmetry_with_macos() -> None:
    source = 'def route() -> str:\n    return "/home/dashboard"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("/home/dashboard" in each_issue for each_issue in issues), (
        f"Linux '/home/<segment>' is structurally indistinguishable from a real"
        f" home directory and must flag for symmetry with macOS, got: {issues}"
    )


def test_should_not_flag_standalone_users_segment_without_trailing_path() -> None:
    source = 'def system_path() -> str:\n    return "/Users/Shared"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"'/Users/Shared' without trailing path component is not navigating into a user home, got: {issues}"
    )


def test_should_skip_hook_infrastructure_files() -> None:
    source = (
        'HARDCODED_USER_PATH_PATTERN = "/Users/[^/]+|/home/[^/]+"\n'
        'def find() -> str:\n'
        '    return "C:/Users/jon/notes.md"\n'
    )
    issues = check_hardcoded_user_paths(source, HOOK_INFRASTRUCTURE_FILE_PATH)
    assert issues == [], (
        f"Hook infrastructure files exempt — the enforcer itself encodes user-path"
        f" patterns and would otherwise self-block, got: {issues}"
    )


def test_should_not_flag_docstring_mentioning_user_path() -> None:
    source = (
        'def load_data() -> None:\n'
        '    """Reads from /home/alice/data for testing."""\n'
        '    pass\n'
    )
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Docstrings are allowed to mention paths, got: {issues}"
    )


def test_should_flag_linux_home_path_when_home_is_entire_path() -> None:
    source = 'def find() -> str:\n    return "/home/alice"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert any("/home/alice" in each_issue for each_issue in issues), (
        f"Expected Linux home literal flagged without trailing slash, got: {issues}"
    )


def test_should_not_flag_windows_public_shared_folder() -> None:
    source = 'def find() -> str:\n    return "C:/Users/Public/Documents"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'C:/Users/Public' is a system shared folder, not a user home, got: {issues}"
    )


def test_should_not_flag_windows_shared_folder() -> None:
    source = 'def find() -> str:\n    return "C:/Users/Shared/data"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'C:/Users/Shared' is a system shared folder, not a user home, got: {issues}"
    )


def test_should_not_flag_windows_all_users_folder() -> None:
    source = 'def find() -> str:\n    return "C:/Users/All Users/AppData"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'C:/Users/All Users' is a legacy shared folder, not a user home, got: {issues}"
    )


def test_should_not_flag_macos_public_shared_folder() -> None:
    source = 'def find() -> str:\n    return "/Users/Public/Documents"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"macOS '/Users/Public' is a default shared folder on every macOS install,"
        f" not a user home — symmetry with the Windows exclusion, got: {issues}"
    )


def test_should_not_flag_windows_lowercase_public_shared_folder() -> None:
    source = 'def find() -> str:\n    return "c:/users/public/Documents"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'c:/users/public' is the same shared folder regardless of case,"
        f" the exclusion list must be case-insensitive, got: {issues}"
    )


def test_should_not_flag_windows_lowercase_shared_folder() -> None:
    source = 'def find() -> str:\n    return "c:/users/shared/data"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'c:/users/shared' is a system shared folder regardless of case,"
        f" got: {issues}"
    )


def test_should_not_flag_windows_lowercase_all_users_folder() -> None:
    source = 'def find() -> str:\n    return "c:/users/all users/AppData"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'c:/users/all users' is a legacy shared folder regardless of case,"
        f" got: {issues}"
    )


def test_should_not_flag_windows_mixed_case_public_shared_folder() -> None:
    source = 'def find() -> str:\n    return "C:/Users/PuBlIc/Documents"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'C:/Users/PuBlIc' is the same shared folder in any casing,"
        f" got: {issues}"
    )


def test_should_not_flag_windows_uppercase_public_shared_folder() -> None:
    source = 'def find() -> str:\n    return "C:/Users/PUBLIC/Documents"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Windows 'C:/Users/PUBLIC' is the same shared folder in any casing,"
        f" got: {issues}"
    )


def test_should_not_flag_macos_lowercase_shared_folder() -> None:
    source = 'def find() -> str:\n    return "/Users/shared/data"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"macOS '/Users/shared' is a system shared folder regardless of case,"
        f" got: {issues}"
    )


def test_should_not_flag_macos_lowercase_public_shared_folder() -> None:
    source = 'def find() -> str:\n    return "/Users/public/Documents"\n'
    issues = check_hardcoded_user_paths(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"macOS '/Users/public' is a default shared folder regardless of case,"
        f" got: {issues}"
    )
