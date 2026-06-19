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


def test_flags_field_set_only_by_constructor_keyword_and_read_nowhere(
    neutral_root: Path,
) -> None:
    """A field set ONLY by a ``*Config`` constructor keyword, read nowhere, is dead.

    A constructor keyword writes the field; it is not a read. When ``debug_port``
    is set by ``ThemeUpdateConfig(debug_port=1)`` and read through no config
    instance anywhere in production, tuning it has no effect, so it is flagged as
    dead config (CODE_RULES §9.8).
    """
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def build() -> ThemeUpdateConfig:\n"
        "    configuration = ThemeUpdateConfig(portal_url='x', debug_port=1, timeout_seconds=99)\n"
        "    print(configuration.portal_url)\n"
        "    print(configuration.timeout_seconds)\n"
        "    return configuration\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"Field set only by constructor keyword and read nowhere must be flagged, got: {issues}"
    )
    assert not any(
        "'portal_url'" in each_issue or "'timeout_seconds'" in each_issue for each_issue in issues
    ), f"Fields read through the config instance must not be flagged, got: {issues}"


def test_qualified_config_constructor_keyword_does_not_clear_field(
    neutral_root: Path,
) -> None:
    """A qualified ``module.ThemeUpdateConfig(field=value)`` keyword is a write, not a read.

    The constructor callee may be a qualified attribute (``config_module.ThemeUpdateConfig``)
    rather than a bare name. Its keyword still writes the field, so a field set only
    this way and read through no config instance is flagged dead.
    """
    consumer_body = (
        "import os_update_workflow.config as config_module\n"
        "\n"
        "def build() -> config_module.ThemeUpdateConfig:\n"
        "    configuration = config_module.ThemeUpdateConfig(\n"
        "        portal_url='x', debug_port=1, timeout_seconds=99\n"
        "    )\n"
        "    print(configuration.portal_url)\n"
        "    print(configuration.timeout_seconds)\n"
        "    return configuration\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"A qualified config constructor keyword is a write, so debug_port is flagged, got: {issues}"
    )


def test_does_not_flag_field_set_by_constructor_keyword_and_read_elsewhere(
    neutral_root: Path,
) -> None:
    """A field set by a constructor keyword AND read via attribute elsewhere is live.

    The constructor keyword does not clear the field, but a genuine attribute read
    of the same field in another module does, so the field is not flagged.
    """
    builder_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def build() -> ThemeUpdateConfig:\n"
        "    return ThemeUpdateConfig(portal_url='x', debug_port=1, timeout_seconds=99)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, builder_body
    )
    reader_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def connect(configuration: ThemeUpdateConfig) -> int:\n"
        "    return configuration.debug_port\n"
    )
    (config_path.parent.parent / "reader.py").write_text(reader_body, encoding="utf-8")
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert not any("'debug_port'" in each_issue for each_issue in issues), (
        f"An attribute read in another module keeps debug_port live, got: {issues}"
    )


def test_flags_field_set_by_default_and_constructor_keyword_only(
    neutral_root: Path,
) -> None:
    """The PR #317 dead-config shape: field set by config default + constructor keyword only.

    ``AppInfoConfig.sound_upload_max_attempts: int = submission_timing.sound_upload_max_attempts``
    sets the field from a same-named attribute on another object inside the config
    body, and the orchestrator sets ``sound_upload_timeout_ms`` by a constructor
    keyword. Neither field is read through any config instance. The default-value
    read inside the config body and the constructor keyword are both writes, so
    both fields are flagged dead.

    Residual limitation: when a consumer module's constructor VALUE expression
    itself reads a same-named attribute on a different object
    (``AppInfoConfig(field=other.field)``), the object-blind attribute-read
    collector counts ``field`` as read and the field escapes. This test keeps the
    constructor value a literal so the keyword-write and default-write exclusions
    are exercised without that foreign-attribute leak.
    """
    config_body = (
        "from dataclasses import dataclass\n"
        "import submission_timing_module as submission_timing\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class AppInfoConfig:\n"
        "    sound_upload_timeout_ms: int = submission_timing.sound_upload_timeout_ms\n"
        "    sound_upload_max_attempts: int = submission_timing.sound_upload_max_attempts\n"
    )
    workflow_directory = neutral_root / "workflow"
    config_package = workflow_directory / "os_update_workflow"
    config_package.mkdir(parents=True)
    (config_package / "__init__.py").write_text("", encoding="utf-8")
    config_path = config_package / "config.py"
    config_path.write_text(config_body, encoding="utf-8")
    orchestrator_body = (
        "from os_update_workflow.config import AppInfoConfig\n"
        "\n"
        "def build() -> AppInfoConfig:\n"
        "    config = AppInfoConfig(sound_upload_timeout_ms=60000)\n"
        "    return config\n"
    )
    (workflow_directory / "orchestrator.py").write_text(orchestrator_body, encoding="utf-8")
    issues = _check(config_body, str(config_path))
    assert any("'sound_upload_timeout_ms'" in each_issue for each_issue in issues), (
        f"Field set by constructor keyword and read nowhere must be flagged, got: {issues}"
    )
    assert any("'sound_upload_max_attempts'" in each_issue for each_issue in issues), (
        f"Field set by config default only and read nowhere must be flagged, got: {issues}"
    )


def test_does_not_flag_config_default_field_read_through_instance(
    neutral_root: Path,
) -> None:
    """A field whose default reads a foreign attribute but is read through the instance is live.

    The default-value exclusion only drops the self-referential read inside the
    config body; a genuine ``config.sound_upload_timeout_ms`` read in production
    keeps the field live.
    """
    config_body = (
        "from dataclasses import dataclass\n"
        "import submission_timing_module as submission_timing\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class AppInfoConfig:\n"
        "    sound_upload_timeout_ms: int = submission_timing.sound_upload_timeout_ms\n"
    )
    workflow_directory = neutral_root / "workflow"
    config_package = workflow_directory / "os_update_workflow"
    config_package.mkdir(parents=True)
    (config_package / "__init__.py").write_text("", encoding="utf-8")
    config_path = config_package / "config.py"
    config_path.write_text(config_body, encoding="utf-8")
    processor_body = (
        "from os_update_workflow.config import AppInfoConfig\n"
        "\n"
        "def wait(config: AppInfoConfig) -> int:\n"
        "    return config.sound_upload_timeout_ms\n"
    )
    (workflow_directory / "processor.py").write_text(processor_body, encoding="utf-8")
    issues = _check(config_body, str(config_path))
    assert issues == [], (
        f"A genuine config-instance read keeps the field live, got: {issues}"
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


def test_flags_field_read_only_via_whole_instance_comparison(neutral_root: Path) -> None:
    """A field read ONLY via whole-instance comparison IS flagged (accepted limitation).

    Unlike the per-file dead-dataclass-field check, this cross-module check does
    not suppress on a dataclass-dunder whole-instance read: instance comparison
    (``left == right``) is not bound to a config instance, and tree-wide one
    incidental ``==`` anywhere would disable the check on any realistic package.
    A ``*Config`` field whose only production read is this whole-instance
    comparison, and that is never read directly, is therefore flagged — a
    documented, rare limitation.
    """
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
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"Field read only via whole-instance comparison is flagged, got: {issues}"
    )


def test_flags_field_read_only_via_whole_instance_stringification(neutral_root: Path) -> None:
    """A field read ONLY via whole-instance stringification IS flagged (accepted limitation).

    The cross-module check does not suppress on a formatted-string conversion of
    a whole instance (``f'{configuration}'``): the f-string is not bound to a
    config instance, and tree-wide one incidental f-string anywhere would disable
    the check on any realistic package. A ``*Config`` field whose only production
    read is this whole-instance stringification, and that is never read directly,
    is therefore flagged — a documented, rare limitation.
    """
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
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"Field read only via whole-instance stringification is flagged, got: {issues}"
    )


def test_unrelated_string_method_does_not_suppress_so_dead_field_flagged(
    neutral_root: Path,
) -> None:
    """An unrelated ``.replace(...)`` on a string must not suppress the tree.

    ``"some text".replace("a", "b")`` is a string method, not a ``dataclasses``-
    qualified reflective consumer, so it does not make the check treat the tree
    as a whole-instance read. A genuinely dead ``debug_port`` is still flagged.
    """
    consumer_body = (
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def run(configuration: ThemeUpdateConfig) -> str:\n"
        "    print(configuration.portal_url)\n"
        "    print(configuration.timeout_seconds)\n"
        "    return 'some text'.replace('a', 'b')\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert any("'debug_port'" in each_issue for each_issue in issues), (
        f"Unrelated string .replace must not suppress, so dead debug_port is flagged, got: {issues}"
    )


def test_dataclasses_qualified_replace_call_suppresses_so_no_field_flagged(
    neutral_root: Path,
) -> None:
    """A ``dataclasses.replace(cfg, ...)`` call suppresses the whole tree.

    A genuine ``dataclasses``-qualified reflective consumer reads every field at
    once, so the check is suppressed for the whole tree and no field is flagged.
    """
    consumer_body = (
        "import dataclasses\n"
        "from os_update_workflow.config import ThemeUpdateConfig\n"
        "\n"
        "def repoint(configuration: ThemeUpdateConfig) -> ThemeUpdateConfig:\n"
        "    return dataclasses.replace(configuration, debug_port=9999)\n"
    )
    config_path = _build_config_package(
        neutral_root / "workflow", THEME_UPDATE_CONFIG_BODY, consumer_body
    )
    issues = _check(THEME_UPDATE_CONFIG_BODY, str(config_path))
    assert issues == [], (
        f"dataclasses.replace reads every field at once, so none may be flagged, got: {issues}"
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
