"""Behavioral tests for post-slice pytest collection gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    COLLECTION_SKIP_DISABLED,
    COLLECTION_SKIP_NO_ON_DISK_TESTS,
    COLLECTION_SKIP_NO_TEST_PATHS,
    COLLECTION_SKIP_PYTEST_UNAVAILABLE,
    PAYLOAD_KEY_CHECKED,
    PAYLOAD_KEY_COLLECTION_ERROR,
    PAYLOAD_KEY_PASSED,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    PAYLOAD_KEY_TEST_PATHS,
)
from validate_slice_collection import (  # noqa: E402
    format_collection_failure_message,
    is_pytest_collectable_path,
    run_pytest_collect_only,
    select_collectable_paths,
    validate_slice_collection,
)

BRANCH_NAME = "split/99/01-backend"
COLLECTABLE_TEST_PATH = "pkg/tests/test_service.py"
PRODUCTION_MODULE_PATH = "pkg/service.py"
NON_TEST_PYTHON_PATH = "pkg/helpers.py"
MISSING_TEST_PATH = "pkg/tests/test_missing.py"


def test_is_pytest_collectable_path_accepts_test_modules() -> None:
    assert is_pytest_collectable_path("pkg/tests/test_service.py") is True
    assert is_pytest_collectable_path("pkg/service_test.py") is True
    assert is_pytest_collectable_path("pkg/service.py") is False
    assert is_pytest_collectable_path("pkg/tests/conftest.py") is False
    assert is_pytest_collectable_path("README.md") is False


def test_select_collectable_paths_filters_and_dedupes() -> None:
    all_paths = [
        COLLECTABLE_TEST_PATH,
        PRODUCTION_MODULE_PATH,
        COLLECTABLE_TEST_PATH,
        NON_TEST_PYTHON_PATH,
    ]
    assert select_collectable_paths(all_paths) == [COLLECTABLE_TEST_PATH]


def test_validate_slice_collection_skips_when_disabled(tmp_path: Path) -> None:
    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[COLLECTABLE_TEST_PATH],
        branch_name=BRANCH_NAME,
        is_enabled=False,
    )
    assert report[PAYLOAD_KEY_SKIPPED] is True
    assert report[PAYLOAD_KEY_SKIP_REASON] == COLLECTION_SKIP_DISABLED
    assert report[PAYLOAD_KEY_CHECKED] is False
    assert report[PAYLOAD_KEY_PASSED] is True


def test_validate_slice_collection_skips_when_no_test_paths(tmp_path: Path) -> None:
    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[PRODUCTION_MODULE_PATH],
        branch_name=BRANCH_NAME,
        is_enabled=True,
    )
    assert report[PAYLOAD_KEY_SKIPPED] is True
    assert report[PAYLOAD_KEY_SKIP_REASON] == COLLECTION_SKIP_NO_TEST_PATHS
    assert report[PAYLOAD_KEY_PASSED] is True


def test_validate_slice_collection_skips_when_tests_not_on_disk(tmp_path: Path) -> None:
    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[MISSING_TEST_PATH],
        branch_name=BRANCH_NAME,
        is_enabled=True,
    )
    assert report[PAYLOAD_KEY_SKIPPED] is True
    assert report[PAYLOAD_KEY_SKIP_REASON] == COLLECTION_SKIP_NO_ON_DISK_TESTS
    assert report[PAYLOAD_KEY_PASSED] is True


def test_validate_slice_collection_passes_when_collect_succeeds(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / COLLECTABLE_TEST_PATH
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok() -> None:\n    assert True\n", encoding="utf-8")

    def run_collect_success(
        repo_root: Path,
        all_test_paths: list[str],
    ) -> subprocess.CompletedProcess[str]:
        assert repo_root == tmp_path
        assert all_test_paths == [COLLECTABLE_TEST_PATH]
        return subprocess.CompletedProcess(
            args=["pytest"],
            returncode=0,
            stdout="1 test collected\n",
            stderr="",
        )

    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[COLLECTABLE_TEST_PATH, PRODUCTION_MODULE_PATH],
        branch_name=BRANCH_NAME,
        is_enabled=True,
        run_collect=run_collect_success,
    )
    assert report[PAYLOAD_KEY_SKIPPED] is False
    assert report[PAYLOAD_KEY_CHECKED] is True
    assert report[PAYLOAD_KEY_PASSED] is True
    assert report[PAYLOAD_KEY_TEST_PATHS] == [COLLECTABLE_TEST_PATH]


def test_validate_slice_collection_fails_on_import_error_collection(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / COLLECTABLE_TEST_PATH
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "from pkg.missing import SYMBOL\n\ndef test_broken() -> None:\n    assert SYMBOL\n",
        encoding="utf-8",
    )
    collect_detail = "ERROR collecting pkg/tests/test_service.py\nImportError: cannot import name SYMBOL"

    def run_collect_failure(
        repo_root: Path,
        all_test_paths: list[str],
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["pytest"],
            returncode=2,
            stdout="",
            stderr=collect_detail,
        )

    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[COLLECTABLE_TEST_PATH],
        branch_name=BRANCH_NAME,
        is_enabled=True,
        run_collect=run_collect_failure,
    )
    assert report[PAYLOAD_KEY_SKIPPED] is False
    assert report[PAYLOAD_KEY_CHECKED] is True
    assert report[PAYLOAD_KEY_PASSED] is False
    assert COLLECTABLE_TEST_PATH in str(report[PAYLOAD_KEY_COLLECTION_ERROR])
    assert "ImportError" in str(report[PAYLOAD_KEY_COLLECTION_ERROR])


def test_validate_slice_collection_soft_skips_when_pytest_missing(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / COLLECTABLE_TEST_PATH
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok() -> None:\n    assert True\n", encoding="utf-8")

    def run_collect_no_pytest(
        repo_root: Path,
        all_test_paths: list[str],
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["python", "-m", "pytest"],
            returncode=1,
            stdout="",
            stderr="No module named pytest",
        )

    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[COLLECTABLE_TEST_PATH],
        branch_name=BRANCH_NAME,
        is_enabled=True,
        run_collect=run_collect_no_pytest,
    )
    assert report[PAYLOAD_KEY_SKIPPED] is True
    assert report[PAYLOAD_KEY_SKIP_REASON] == COLLECTION_SKIP_PYTEST_UNAVAILABLE
    assert report[PAYLOAD_KEY_PASSED] is True


def test_validate_slice_collection_default_runner_collects_real_file(
    tmp_path: Path,
) -> None:
    package_directory = tmp_path / "sample_pkg"
    package_directory.mkdir()
    (package_directory / "__init__.py").write_text("", encoding="utf-8")
    (package_directory / "widget.py").write_text(
        "WIDGET_NAME = 'ok'\n",
        encoding="utf-8",
    )
    test_directory = package_directory / "tests"
    test_directory.mkdir()
    (test_directory / "__init__.py").write_text("", encoding="utf-8")
    test_path = "sample_pkg/tests/test_widget.py"
    (tmp_path / test_path).write_text(
        "from sample_pkg.widget import WIDGET_NAME\n\n"
        "def test_widget_name() -> None:\n"
        "    assert WIDGET_NAME == 'ok'\n",
        encoding="utf-8",
    )
    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[test_path, "sample_pkg/widget.py"],
        branch_name=BRANCH_NAME,
        is_enabled=True,
    )
    assert report[PAYLOAD_KEY_PASSED] is True
    assert report[PAYLOAD_KEY_CHECKED] is True


def test_format_collection_failure_message_includes_branch_and_detail() -> None:
    report = {
        PAYLOAD_KEY_COLLECTION_ERROR: "ImportError: cannot import name build_token",
    }
    message = format_collection_failure_message(BRANCH_NAME, report)
    assert BRANCH_NAME in message
    assert "wrong side of the cut" in message
    assert "ImportError" in message


def test_run_pytest_collect_only_returns_completed_process(tmp_path: Path) -> None:
    test_path = "sample_pkg/tests/test_widget.py"
    package_directory = tmp_path / "sample_pkg"
    package_directory.mkdir()
    (package_directory / "__init__.py").write_text("", encoding="utf-8")
    test_directory = package_directory / "tests"
    test_directory.mkdir()
    (test_directory / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / test_path).write_text(
        "def test_widget_name() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    completed = run_pytest_collect_only(tmp_path, [test_path])
    assert completed.returncode == 0
    assert "test" in (completed.stdout or "").lower() or completed.returncode == 0


def test_validate_slice_collection_default_runner_flags_missing_definition(
    tmp_path: Path,
) -> None:
    package_directory = tmp_path / "sample_pkg"
    package_directory.mkdir()
    (package_directory / "__init__.py").write_text("", encoding="utf-8")
    test_directory = package_directory / "tests"
    test_directory.mkdir()
    (test_directory / "__init__.py").write_text("", encoding="utf-8")
    test_path = "sample_pkg/tests/test_widget.py"
    (tmp_path / test_path).write_text(
        "from sample_pkg.widget import WIDGET_NAME\n\n"
        "def test_widget_name() -> None:\n"
        "    assert WIDGET_NAME == 'ok'\n",
        encoding="utf-8",
    )
    report = validate_slice_collection(
        repo_root=tmp_path,
        all_paths=[test_path],
        branch_name=BRANCH_NAME,
        is_enabled=True,
    )
    assert report[PAYLOAD_KEY_PASSED] is False
    assert report[PAYLOAD_KEY_CHECKED] is True
    assert report[PAYLOAD_KEY_COLLECTION_ERROR]
