from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
assert specification is not None and specification.loader is not None
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/report.py"
TEST_FILE_PATH = "packages/app/services/test_report.py"
MIGRATION_FILE_PATH = "packages/app/migrations/0001_initial.py"

THEME_UPDATE_CONFIG_BODY = (
    "from dataclasses import dataclass\n"
    "\n"
    "@dataclass\n"
    "class ThemeUpdateConfig:\n"
    "    portal_url: str\n"
    "    debug_port: int\n"
    "    timeout_seconds: int\n"
)


def _strip_read_only_and_retry(
    removal_function: Callable[[str], object],
    target_path: str,
    _exc_info: BaseException,
) -> None:
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


@pytest.fixture
def neutral_root() -> Iterator[Path]:
    """Yield a temp directory whose path carries no ``test_`` segment.

    The enforcer's ``is_test_file`` keys on the full path string, and pytest's
    own ``tmp_path`` directory name embeds the test name, which would make every
    synthetic config path look like a test file. A neutral ``mkdtemp`` root
    mirrors how a production config module path looks.
    """
    neutral_directory = Path(tempfile.mkdtemp(prefix="deadcfg-")).resolve()
    try:
        yield neutral_directory
    finally:
        shutil.rmtree(neutral_directory, onexc=_strip_read_only_and_retry)


def _check(source: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_dead_config_dataclass_fields(source, file_path)


def _build_config_package(
    workflow_directory: Path,
    config_body: str,
    consumer_body: str,
) -> Path:
    config_package = workflow_directory / "os_update_workflow"
    config_package.mkdir(parents=True)
    (config_package / "__init__.py").write_text("", encoding="utf-8")
    config_path = config_package / "config.py"
    config_path.write_text(config_body, encoding="utf-8")
    (workflow_directory / "runner.py").write_text(consumer_body, encoding="utf-8")
    return config_path


def test_flags_config_field_read_by_no_production_module(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def run(configuration: ThemeUpdateConfig) -> None:\n"
        "    print(configuration.portal_url)\n"
        "    print(configuration.timeout_seconds)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"Expected dead 'debug_port' flagged, got: {issues}"
    )
    assert not any(
        "'portal_url'" in each_issue or "'timeout_seconds'" in each_issue for each_issue in issues
    ), f"Fields read in consumer must not be flagged, got: {issues}"


def test_does_not_flag_field_read_as_attribute_in_sibling_module(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def run(configuration: ThemeUpdateConfig) -> None:\n"
        "    print(configuration.portal_url)\n"
        "    print(configuration.debug_port)\n"
        "    print(configuration.timeout_seconds)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], f"All fields are read in consumer, none must be flagged, got: {issues}"


def test_flags_field_read_only_by_test_module(neutral_root: Path) -> None:
    workflow_directory = neutral_root / "workflow"
    config_package = workflow_directory / "os_update_workflow"
    config_package.mkdir(parents=True)
    (config_package / "__init__.py").write_text("", encoding="utf-8")
    config_path = config_package / "config.py"
    config_path.write_text(THEME_UPDATE_CONFIG_BODY, encoding="utf-8")
    test_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def test_debug_port_default() -> None:\n"
        "    cfg = ThemeUpdateConfig(portal_url='x', debug_port=9222, timeout_seconds=30)\n"
        "    assert cfg.debug_port == 9222\n"
        "    assert cfg.portal_url == 'x'\n"
        "    assert cfg.timeout_seconds == 30\n"
    )
    (workflow_directory / "test_config.py").write_text(test_body, encoding="utf-8")
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"Field read only by test code must still be flagged as dead-in-production, got: {issues}"
    )


def test_ignores_non_config_named_dataclass(neutral_root: Path) -> None:
    source = (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class ThemeMetadata:\n"
        "    title: str\n"
        "    debug_port: int\n"
    )
    workflow_directory = neutral_root / "workflow"
    workflow_directory.mkdir(parents=True)
    module_path = workflow_directory / "metadata.py"
    module_path.write_text(source, encoding="utf-8")
    issues = _check(source, str(module_path))
    assert issues == [], (
        f"Non-Config-named dataclasses are outside scope of this check, got: {issues}"
    )


def test_does_not_flag_field_read_via_string_literal(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def read_field(configuration: ThemeUpdateConfig, field_name: str) -> object:\n"
        "    return getattr(configuration, 'debug_port')\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert not any("'debug_port'" in each_issue for each_issue in issues), (
        f"String literal getattr read must count as a field read, got: {issues}"
    )


def test_does_not_flag_when_consumer_serializes_whole_instance_via_asdict(
    neutral_root: Path,
) -> None:
    consumer_body = (
        "from dataclasses import asdict\n"
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def serialize(configuration: ThemeUpdateConfig) -> dict[str, object]:\n"
        "    return asdict(configuration)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], (
        f"asdict reads every field at once, so no field may be flagged, got: {issues}"
    )


def test_does_not_flag_when_consumer_reads_instance_dict(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def serialize(configuration: ThemeUpdateConfig) -> dict[str, object]:\n"
        "    return dict(configuration.__dict__)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], (
        f"__dict__ read consumes every field at once, so none may be flagged, got: {issues}"
    )


def test_does_not_flag_field_used_only_as_replace_keyword(neutral_root: Path) -> None:
    consumer_body = (
        "from dataclasses import replace\n"
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def repoint(configuration: ThemeUpdateConfig) -> ThemeUpdateConfig:\n"
        "    return replace(configuration, debug_port=9999)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert not any("'debug_port'" in each_issue for each_issue in issues), (
        f"replace keyword usage of debug_port must count as a read, got: {issues}"
    )


def test_does_not_flag_field_used_only_as_constructor_keyword(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def build() -> ThemeUpdateConfig:\n"
        "    return ThemeUpdateConfig(portal_url='x', debug_port=1, timeout_seconds=99)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], (
        f"Constructor keyword arguments name every field, so none may be flagged, got: {issues}"
    )


def test_returns_empty_list_at_file_cap(
    neutral_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("code_rules_dead_config_field.MAX_SCAN_ROOT_FILE_COUNT", 0)
    config_path = _build_config_package(
        neutral_root / "workflow",
        THEME_UPDATE_CONFIG_BODY,
        "def noop() -> None:\n    pass\n",
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], f"File cap hit must return [] (cannot prove dead), got: {issues}"


def test_returns_empty_list_on_syntax_error(neutral_root: Path) -> None:
    workflow_directory = neutral_root / "workflow"
    workflow_directory.mkdir(parents=True)
    broken_path = workflow_directory / "config.py"
    broken_source = "@dataclass\nclass BrokenConfig(\n"
    broken_path.write_text(broken_source, encoding="utf-8")
    issues = _check(broken_source, str(broken_path))
    assert issues == [], f"SyntaxError must return [], got: {issues}"


def test_is_skipped_on_test_file_destination() -> None:
    issues = _check(THEME_UPDATE_CONFIG_BODY, TEST_FILE_PATH)
    assert issues == [], f"Test file destinations are exempt, got: {issues}"


def test_is_skipped_on_migration_file_destination() -> None:
    issues = _check(THEME_UPDATE_CONFIG_BODY, MIGRATION_FILE_PATH)
    assert issues == [], f"Migration file destinations are exempt, got: {issues}"


def test_real_world_shape_theme_update_config_with_dead_debug_port(neutral_root: Path) -> None:
    workflow_directory = neutral_root / "workflow"
    config_package = workflow_directory / "os_update_workflow"
    config_package.mkdir(parents=True)
    (config_package / "__init__.py").write_text("", encoding="utf-8")
    config_path = config_package / "config.py"
    config_path.write_text(THEME_UPDATE_CONFIG_BODY, encoding="utf-8")
    orchestrator_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def build_session(configuration: ThemeUpdateConfig) -> None:\n"
        "    url = configuration.portal_url\n"
        "    seconds = configuration.timeout_seconds\n"
        "    print(url, seconds)\n"
    )
    (workflow_directory / "orchestrator.py").write_text(orchestrator_body, encoding="utf-8")
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"debug_port field unused in production must be flagged, got: {issues}"
    )
    assert not any(
        "'portal_url'" in each_issue or "'timeout_seconds'" in each_issue for each_issue in issues
    ), f"Fields read in orchestrator must not be flagged, got: {issues}"


def test_does_not_flag_field_used_only_via_augmented_assignment(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def run(configuration: ThemeUpdateConfig) -> None:\n"
        "    print(configuration.portal_url)\n"
        "    print(configuration.timeout_seconds)\n"
        "    configuration.debug_port += 1\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert not any("'debug_port'" in each_issue for each_issue in issues), (
        f"Augmented assignment reads debug_port before writing, so it is not dead, got: {issues}"
    )


def test_does_not_flag_when_consumer_compares_whole_instance(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def is_same(left: ThemeUpdateConfig, right: ThemeUpdateConfig) -> bool:\n"
        "    return left == right\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], (
        f"Comparing instances reads every field via __eq__, so none may be flagged, got: {issues}"
    )


def test_does_not_flag_when_consumer_stringifies_whole_instance(neutral_root: Path) -> None:
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def describe(configuration: ThemeUpdateConfig) -> str:\n"
        "    return f'{configuration}'\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], (
        f"Formatted-string conversion reads every field via __repr__, so none may be flagged, got: {issues}"
    )


def test_validate_content_dispatch_runs_dead_config_field_check(neutral_root: Path) -> None:
    workflow_directory = neutral_root / "workflow"
    config_package = workflow_directory / "os_update_workflow"
    config_package.mkdir(parents=True)
    (config_package / "__init__.py").write_text("", encoding="utf-8")
    config_path = config_package / "config.py"
    config_path.write_text(THEME_UPDATE_CONFIG_BODY, encoding="utf-8")
    (workflow_directory / "runner.py").write_text(
        "def noop() -> None:\n    pass\n", encoding="utf-8"
    )
    issues = code_rules_enforcer.validate_content(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"Expected the enforcer dispatch to surface the dead config field, got: {issues}"
    )
