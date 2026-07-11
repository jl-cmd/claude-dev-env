"""Tests for check_config_duplicate_path_anchor.

Directories come from ``tmp_path_factory.mktemp`` with a neutral name because
the per-test ``tmp_path`` embeds the test function name, and that name would
make the test-path exemption inside the validator swallow every case.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ENFORCER_FILENAME = "code_rules_enforcer.py"
ENFORCER_MODULE_NAME = "code_rules_enforcer_duplicate_anchor_tests"
SIBLING_MODULE_SOURCE = """\
from pathlib import Path

NEON_SUBMISSION_LOG_DIRECTORY = Path(__file__).resolve().parents[2] / "logs" / "theme_submissions"
"""
WRITTEN_MODULE_SOURCE = """\
from pathlib import Path

LOG_BASE_DIR = Path(__file__).resolve().parents[2] / "logs"
THEME_SUBMISSIONS_LOG_FOLDER = "theme_submissions"
"""


def load_enforcer_module() -> ModuleType:
    loader_path = Path(__file__).parent / ENFORCER_FILENAME
    module_spec = importlib.util.spec_from_file_location(ENFORCER_MODULE_NAME, loader_path)
    assert module_spec is not None
    assert module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


enforcer = load_enforcer_module()


def _config_directory_with_sibling(
    tmp_path_factory: pytest.TempPathFactory, sibling_source: str
) -> Path:
    config_directory = tmp_path_factory.mktemp("workspace_home") / "config"
    config_directory.mkdir()
    (config_directory / "neon_submission.py").write_text(sibling_source, encoding="utf-8")
    return config_directory


def test_should_flag_reanchored_base_already_built_by_sibling(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    config_directory = _config_directory_with_sibling(tmp_path_factory, SIBLING_MODULE_SOURCE)
    written_path = str(config_directory / "derived_paths.py")
    issues = enforcer.check_config_duplicate_path_anchor(WRITTEN_MODULE_SOURCE, written_path)
    assert len(issues) == 1
    assert "neon_submission.py" in issues[0]


def test_should_flag_parent_chain_anchor_matching_sibling_parents_index(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    config_directory = _config_directory_with_sibling(tmp_path_factory, SIBLING_MODULE_SOURCE)
    written_source = """\
from pathlib import Path

LOG_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
"""
    written_path = str(config_directory / "derived_paths.py")
    issues = enforcer.check_config_duplicate_path_anchor(written_source, written_path)
    assert len(issues) == 1


def test_should_allow_anchor_with_different_first_segment(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    config_directory = _config_directory_with_sibling(tmp_path_factory, SIBLING_MODULE_SOURCE)
    written_source = """\
from pathlib import Path

SNAPSHOT_BASE_DIR = Path(__file__).resolve().parents[2] / "snapshots"
"""
    written_path = str(config_directory / "derived_paths.py")
    issues = enforcer.check_config_duplicate_path_anchor(written_source, written_path)
    assert issues == []


def test_should_allow_anchor_with_different_depth(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    config_directory = _config_directory_with_sibling(tmp_path_factory, SIBLING_MODULE_SOURCE)
    written_source = """\
from pathlib import Path

LOG_BASE_DIR = Path(__file__).resolve().parents[3] / "logs"
"""
    written_path = str(config_directory / "derived_paths.py")
    issues = enforcer.check_config_duplicate_path_anchor(written_source, written_path)
    assert issues == []


def test_should_allow_module_with_no_sibling_config_files(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    config_directory = tmp_path_factory.mktemp("workspace_home") / "config"
    config_directory.mkdir()
    written_path = str(config_directory / "derived_paths.py")
    issues = enforcer.check_config_duplicate_path_anchor(WRITTEN_MODULE_SOURCE, written_path)
    assert issues == []


def test_should_skip_modules_outside_config_directories(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    plain_directory = tmp_path_factory.mktemp("workspace_home") / "services"
    plain_directory.mkdir()
    (plain_directory / "neon_submission.py").write_text(SIBLING_MODULE_SOURCE, encoding="utf-8")
    written_path = str(plain_directory / "derived_paths.py")
    issues = enforcer.check_config_duplicate_path_anchor(WRITTEN_MODULE_SOURCE, written_path)
    assert issues == []


def test_should_skip_unparseable_sibling_modules(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    config_directory = _config_directory_with_sibling(tmp_path_factory, "def broken(:\n")
    written_path = str(config_directory / "derived_paths.py")
    issues = enforcer.check_config_duplicate_path_anchor(WRITTEN_MODULE_SOURCE, written_path)
    assert issues == []
