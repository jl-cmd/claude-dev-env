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

    ::

        tmp_path (pytest default)    -> embeds "test_..." in its name
                                          -> is_test_file() misreads the path
        mkdtemp(prefix="deadconst-") -> no "test_" segment  ->  reads as
                                          a production path  ok

    A ``.git`` marker is planted at the root so the cross-tree widening
    resolves the repository root to this synthetic tree.
    """
    neutral_directory = Path(tempfile.mkdtemp(prefix="deadconst-")).resolve()
    (neutral_directory / ".git").mkdir()
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


def _assert_alias_read_constants_live(issues: list[str]) -> None:
    assert not any(
        "MEDIUM_TERMINAL" in each_issue or "MEDIUM_CODE" in each_issue for each_issue in issues
    ), f"A constant read as attribute of an imported module stays live, got: {issues}"
    assert any("MEDIUM_TEXT" in each_issue for each_issue in issues), (
        f"A constant read by no module must still be flagged, got: {issues}"
    )


def test_does_not_flag_constant_read_via_from_import_module_alias_attribute(
    neutral_root: Path,
) -> None:
    consumer_body = (
        "from report_constants import render_report_constants as constants\n"
        "\n"
        "def panel_class(medium: str) -> str:\n"
        "    if medium == constants.MEDIUM_TERMINAL:\n"
        "        return 'terminal'\n"
        "    return 'code' if medium == constants.MEDIUM_CODE else 'other'\n"
    )
    constants_path = _build_constants_package(
        neutral_root / "workflow", CONSTANTS_BODY, consumer_body
    )
    _assert_alias_read_constants_live(_check(CONSTANTS_BODY, str(constants_path)))


def test_does_not_flag_constant_read_via_import_as_alias_attribute(
    neutral_root: Path,
) -> None:
    consumer_body = (
        "import report_constants.render_report_constants as constants\n"
        "\n"
        "def label(medium: str) -> str:\n"
        "    if medium == constants.MEDIUM_TERMINAL:\n"
        "        return 'terminal'\n"
        "    return 'code' if medium == constants.MEDIUM_CODE else 'other'\n"
    )
    constants_path = _build_constants_package(
        neutral_root / "workflow", CONSTANTS_BODY, consumer_body
    )
    _assert_alias_read_constants_live(_check(CONSTANTS_BODY, str(constants_path)))


def test_does_not_flag_constant_read_via_plain_module_name_attribute(
    neutral_root: Path,
) -> None:
    consumer_body = (
        "from report_constants import render_report_constants\n"
        "\n"
        "def label(medium: str) -> str:\n"
        "    if medium == render_report_constants.MEDIUM_TERMINAL:\n"
        "        return 'terminal'\n"
        "    if medium == render_report_constants.MEDIUM_CODE:\n"
        "        return 'code'\n"
        "    return 'other'\n"
    )
    constants_path = _build_constants_package(
        neutral_root / "workflow", CONSTANTS_BODY, consumer_body
    )
    _assert_alias_read_constants_live(_check(CONSTANTS_BODY, str(constants_path)))
