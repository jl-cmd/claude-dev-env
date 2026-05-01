from __future__ import annotations

from pathlib import Path
import importlib.util

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location(
    "code_rules_enforcer", ENFORCER_PATH
)
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/foo.py"
TEST_FILE_PATH = "packages/app/tests/test_foo.py"
CONFIG_FILE_PATH = "packages/app/config/constants.py"


def test_should_flag_env_var_name_string_in_function_body() -> None:
    source = (
        "import os\n"
        "\n"
        "def fetch_secret() -> str:\n"
        "    return os.environ['STRIPE_SECRET']\n"
    )
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert any("STRIPE_SECRET" in each_issue for each_issue in issues), (
        f"Expected env-var name flagged, got: {issues}"
    )


def test_should_flag_settings_key_all_caps_with_underscore() -> None:
    source = "def lookup(settings: dict) -> str:\n    return settings['HOOKS_PATH']\n"
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert any("HOOKS_PATH" in each_issue for each_issue in issues), (
        f"Expected settings key flagged, got: {issues}"
    )


def test_should_flag_dotted_segment_string() -> None:
    source = "def is_git_dir(path: str) -> bool:\n    return path.endswith('.git')\n"
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert any(".git" in each_issue for each_issue in issues), (
        f"Expected '.git' flagged, got: {issues}"
    )


def test_should_not_flag_single_letter_uppercase() -> None:
    source = "def is_added(line: str) -> bool:\n    return line.startswith('A')\n"
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Single capital letter must not be flagged, got: {issues}"


def test_should_not_flag_short_uppercase_acronym() -> None:
    source = "def is_get(method: str) -> bool:\n    return method == 'GET'\n"
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Short acronym 'GET' must not be flagged, got: {issues}"


def test_should_not_flag_human_readable_message() -> None:
    source = (
        "def fail() -> None:\n    raise RuntimeError('Could not connect to host')\n"
    )
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Human-readable message must not be flagged, got: {issues}"


def test_should_not_flag_lowercase_string() -> None:
    source = "def get_label() -> str:\n    return 'hello'\n"
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Lowercase string must not be flagged, got: {issues}"


def test_should_not_flag_module_level_string() -> None:
    source = "DEFAULT_KEY = 'STRIPE_SECRET'\n"
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Module-level string must not be flagged (it IS the constant), got: {issues}"
    )


def test_should_not_flag_docstring() -> None:
    source = (
        "def consume() -> None:\n"
        '    """STRIPE_SECRET is documented here for reference."""\n'
        "    return None\n"
    )
    issues = code_rules_enforcer.check_string_literal_magic(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Docstring must not be flagged, got: {issues}"


def test_should_skip_in_test_files() -> None:
    source = (
        "import os\n"
        "\n"
        "def test_env() -> None:\n"
        "    assert os.environ['STRIPE_SECRET'] == 'x'\n"
    )
    issues = code_rules_enforcer.check_string_literal_magic(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues}"


def test_should_skip_in_config_files() -> None:
    source = "def env_keys() -> list[str]:\n    return ['STRIPE_SECRET', 'DB_HOST']\n"
    issues = code_rules_enforcer.check_string_literal_magic(source, CONFIG_FILE_PATH)
    assert issues == [], f"Config files exempt, got: {issues}"
