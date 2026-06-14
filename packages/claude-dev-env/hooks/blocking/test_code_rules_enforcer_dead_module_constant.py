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

CONSTANTS_BODY = 'MEDIUM_TERMINAL = "terminal"\nMEDIUM_CODE = "code"\nMEDIUM_TEXT = "text"\n'


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
    synthetic constants path look like a test file. A neutral ``mkdtemp`` root
    mirrors how a production constants module path looks.
    """
    neutral_directory = Path(tempfile.mkdtemp(prefix="deadconst-")).resolve()
    try:
        yield neutral_directory
    finally:
        shutil.rmtree(neutral_directory, onexc=_strip_read_only_and_retry)


def _check(source: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_dead_module_constants(source, file_path)


def _build_constants_package(
    workflow_directory: Path,
    constants_body: str,
    consumer_body: str,
) -> Path:
    constants_package = workflow_directory / "report_constants"
    constants_package.mkdir(parents=True)
    (constants_package / "__init__.py").write_text("", encoding="utf-8")
    constants_path = constants_package / "render_report_constants.py"
    constants_path.write_text(constants_body, encoding="utf-8")
    (workflow_directory / "render_report.py").write_text(consumer_body, encoding="utf-8")
    return constants_path


def test_flags_constant_imported_by_no_module_in_the_tree(neutral_root: Path) -> None:
    consumer_body = (
        "from report_constants.render_report_constants import (\n"
        "    MEDIUM_CODE,\n"
        "    MEDIUM_TERMINAL,\n"
        ")\n"
        "\n"
        "def panel_class(medium: str) -> str:\n"
        "    if medium == MEDIUM_TERMINAL:\n"
        "        return 'terminal'\n"
        "    return 'code-panel' if medium == MEDIUM_CODE else 'text-panel'\n"
    )
    constants_path = _build_constants_package(
        neutral_root / "workflow", CONSTANTS_BODY, consumer_body
    )
    issues = _check(CONSTANTS_BODY, str(constants_path))
    assert any("MEDIUM_TEXT" in each_issue for each_issue in issues), (
        f"Expected dead MEDIUM_TEXT flagged, got: {issues}"
    )
    assert not any(
        "MEDIUM_TERMINAL" in each_issue or "MEDIUM_CODE" in each_issue for each_issue in issues
    ), f"Imported constants must not be flagged, got: {issues}"


def test_does_not_flag_constant_imported_one_directory_up(neutral_root: Path) -> None:
    consumer_uses_text = (
        "from report_constants.render_report_constants import (\n"
        "    MEDIUM_CODE,\n"
        "    MEDIUM_TERMINAL,\n"
        "    MEDIUM_TEXT,\n"
        ")\n"
        "\n"
        "def panel_class(medium: str) -> str:\n"
        "    if medium == MEDIUM_TERMINAL:\n"
        "        return 'terminal'\n"
        "    if medium == MEDIUM_TEXT:\n"
        "        return 'text-panel'\n"
        "    return 'code-panel' if medium == MEDIUM_CODE else 'text-panel'\n"
    )
    constants_path = _build_constants_package(
        neutral_root / "workflow", CONSTANTS_BODY, consumer_uses_text
    )
    issues = _check(CONSTANTS_BODY, str(constants_path))
    assert issues == [], f"No constant is dead when all are imported, got: {issues}"


def test_does_not_flag_when_module_declares_dunder_all(neutral_root: Path) -> None:
    constants_body = CONSTANTS_BODY + '__all__ = ["MEDIUM_TERMINAL"]\n'
    consumer_body = (
        "from report_constants.render_report_constants import MEDIUM_TERMINAL\n"
        "\n"
        "def label() -> str:\n"
        "    return MEDIUM_TERMINAL\n"
    )
    constants_path = _build_constants_package(
        neutral_root / "workflow", constants_body, consumer_body
    )
    issues = _check(constants_body, str(constants_path))
    assert issues == [], f"__all__ surface suppresses the check, got: {issues}"


def test_does_not_run_on_ordinary_production_module(neutral_root: Path) -> None:
    workflow_directory = neutral_root / "workflow"
    workflow_directory.mkdir(parents=True)
    ordinary_path = workflow_directory / "render_report.py"
    body = "WIDGET_LIMIT = 5\n\ndef widgets() -> int:\n    return WIDGET_LIMIT\n"
    ordinary_path.write_text(body, encoding="utf-8")
    issues = _check(body, str(ordinary_path))
    assert issues == [], (
        f"The dead-constant check runs only on dedicated constants modules, got: {issues}"
    )


def test_runs_on_config_directory_module(neutral_root: Path) -> None:
    package_directory = neutral_root / "app"
    config_directory = package_directory / "config"
    config_directory.mkdir(parents=True)
    constants_body = "TIMEOUT_SECONDS = 30\nUNUSED_THRESHOLD = 99\n"
    constants_path = config_directory / "timing.py"
    constants_path.write_text(constants_body, encoding="utf-8")
    consumer_body = (
        "from config.timing import TIMEOUT_SECONDS\n"
        "\n"
        "def deadline() -> int:\n"
        "    return TIMEOUT_SECONDS\n"
    )
    (package_directory / "service.py").write_text(consumer_body, encoding="utf-8")
    issues = _check(constants_body, str(constants_path))
    assert any("UNUSED_THRESHOLD" in each_issue for each_issue in issues), (
        f"Expected dead UNUSED_THRESHOLD flagged in config module, got: {issues}"
    )
    assert not any("TIMEOUT_SECONDS" in each_issue for each_issue in issues), (
        f"Consumed config constant must not be flagged, got: {issues}"
    )


def test_counts_a_reference_from_a_test_module(neutral_root: Path) -> None:
    workflow_directory = neutral_root / "workflow"
    constants_body = 'ONLY_TESTS_USE_THIS = "x"\n'
    constants_path = workflow_directory / "render_report_constants.py"
    workflow_directory.mkdir(parents=True)
    constants_path.write_text(constants_body, encoding="utf-8")
    test_body = (
        "from render_report_constants import ONLY_TESTS_USE_THIS\n"
        "\n"
        "def test_value() -> None:\n"
        "    assert ONLY_TESTS_USE_THIS == 'x'\n"
    )
    (workflow_directory / "test_render_report.py").write_text(test_body, encoding="utf-8")
    issues = _check(constants_body, str(constants_path))
    assert issues == [], f"A constant used only by a test under the tree stays live, got: {issues}"


def test_is_skipped_on_a_constants_test_file(neutral_root: Path) -> None:
    workflow_directory = neutral_root / "workflow"
    workflow_directory.mkdir(parents=True)
    test_constants_path = workflow_directory / "test_render_report_constants.py"
    body = 'UNREFERENCED = "y"\n'
    test_constants_path.write_text(body, encoding="utf-8")
    issues = _check(body, str(test_constants_path))
    assert issues == [], f"Test files are exempt, got: {issues}"
