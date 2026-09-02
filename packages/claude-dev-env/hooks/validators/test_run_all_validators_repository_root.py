"""Repository-root anchoring tests for the PreToolUse staging walk.

Staging mirrors the destination's exemption-signalling directories through a
temp path so the save-path checks read the same signals the real path carries.
The walk must read only the segments the project itself owns. A directory above
the project root — a home directory named ``tests``, a checkout parked under
``config`` — belongs to whoever laid out the disk, not to the project, and must
never lend a production file a test or config exemption.
"""

from pathlib import Path

import pytest

from .run_all_validators import (
    _temporary_path_preserving_directory_signal,
    validate_proposed_file,
)

pytestmark = pytest.mark.usefixtures("ephemeral_exempt_off")

GIT_MARKER_DIRECTORY_NAME = ".git"
MAGIC_VALUE_CHECK_NAME = "Magic Values"
PRODUCTION_CONTENT_WITH_MAGIC_VALUE = "def retry_budget_seconds() -> int:\n    return 3600 * 7\n"


def _project_root_under(parent_directory: Path) -> Path:
    """Create a git-marked project directory under *parent_directory*.

    Args:
        parent_directory: Directory the project root is created inside.

    Returns:
        The created project root, holding an empty ``.git`` marker directory.
    """
    project_root = parent_directory / "project"
    (project_root / GIT_MARKER_DIRECTORY_NAME).mkdir(parents=True)
    return project_root


def _staged_relative_path(staging_directory: Path, destination_path: Path) -> str:
    """Return the posix staged path *destination_path* produces, relative to staging.

    Args:
        staging_directory: Root of the ephemeral staging tree.
        destination_path: Real destination the write or edit targets.

    Returns:
        The staged path relative to *staging_directory*, in posix form.
    """
    staged_path = _temporary_path_preserving_directory_signal(
        staging_directory, str(destination_path)
    )
    return staged_path.relative_to(staging_directory).as_posix()


def _failed_check_names(destination_path: Path, proposed_content: str) -> list[str]:
    """Return the names of every save-path check that fails for a destination.

    Args:
        destination_path: Real destination the write or edit targets.
        proposed_content: Post-edit content the write would leave on disk.

    Returns:
        The failing check names, in roster order.
    """
    return [
        each_result.name
        for each_result in validate_proposed_file(str(destination_path), proposed_content)
        if not each_result.passed
    ]


def test_should_drop_tests_directory_above_the_project_root(tmp_path: Path) -> None:
    """A home directory named ``tests`` lends no test exemption to project code."""
    parent_named_tests = tmp_path / "tests"
    project_root = _project_root_under(parent_named_tests)
    staging_directory = tmp_path / "staging"
    staging_directory.mkdir()

    staged_relative = _staged_relative_path(staging_directory, project_root / "src" / "worker.py")

    assert staged_relative == "worker.py", (
        f"a tests directory above the project must not stage into the path, got {staged_relative}"
    )


def test_should_drop_config_directory_above_the_project_root(tmp_path: Path) -> None:
    """A checkout parked under ``config`` lends no config exemption to project code."""
    parent_named_config = tmp_path / "config"
    project_root = _project_root_under(parent_named_config)
    staging_directory = tmp_path / "staging"
    staging_directory.mkdir()

    staged_relative = _staged_relative_path(staging_directory, project_root / "src" / "worker.py")

    assert staged_relative == "worker.py", (
        f"a config directory above the project must not stage into the path, got {staged_relative}"
    )


def test_should_report_magic_value_for_production_file_under_a_tests_parent(
    tmp_path: Path,
) -> None:
    """The magic-value check grades project code under a ``tests`` parent directory."""
    project_root = _project_root_under(tmp_path / "tests")

    all_failed_names = _failed_check_names(
        project_root / "src" / "worker.py", PRODUCTION_CONTENT_WITH_MAGIC_VALUE
    )

    assert MAGIC_VALUE_CHECK_NAME in all_failed_names, (
        f"production code under a tests parent must still be graded, got {all_failed_names}"
    )


def test_should_report_magic_value_for_production_file_under_a_config_parent(
    tmp_path: Path,
) -> None:
    """The magic-value check grades project code under a ``config`` parent directory."""
    project_root = _project_root_under(tmp_path / "config")

    all_failed_names = _failed_check_names(
        project_root / "src" / "worker.py", PRODUCTION_CONTENT_WITH_MAGIC_VALUE
    )

    assert MAGIC_VALUE_CHECK_NAME in all_failed_names, (
        f"production code under a config parent must still be graded, got {all_failed_names}"
    )


def test_should_keep_test_helpers_directory_inside_the_project(tmp_path: Path) -> None:
    """A ``test_helpers`` package inside the project keeps its test exemption."""
    project_root = _project_root_under(tmp_path / "tests")
    staging_directory = tmp_path / "staging"
    staging_directory.mkdir()

    staged_relative = _staged_relative_path(
        staging_directory, project_root / "pkg" / "test_helpers" / "worker.py"
    )

    assert staged_relative == "test_helpers/worker.py", (
        f"an in-project test_helpers directory must stage into the path, got {staged_relative}"
    )


def test_should_keep_scripts_directory_inside_the_project(tmp_path: Path) -> None:
    """A ``scripts`` directory inside the project keeps its CLI-marker signal."""
    project_root = _project_root_under(tmp_path / "tests")
    staging_directory = tmp_path / "staging"
    staging_directory.mkdir()

    staged_relative = _staged_relative_path(
        staging_directory, project_root / "scripts" / "deploy.py"
    )

    assert staged_relative == "scripts/deploy.py", (
        f"an in-project scripts directory must stage into the path, got {staged_relative}"
    )


def test_should_keep_tests_directory_inside_the_project(tmp_path: Path) -> None:
    """A genuine ``tests`` directory inside the project keeps its test exemption."""
    project_root = _project_root_under(tmp_path / "config")
    staging_directory = tmp_path / "staging"
    staging_directory.mkdir()

    staged_relative = _staged_relative_path(
        staging_directory, project_root / "tests" / "helpers" / "data.py"
    )

    assert staged_relative == "tests/helpers/data.py", (
        f"an in-project tests directory must stage into the path, got {staged_relative}"
    )


def test_should_keep_config_directory_inside_the_project(tmp_path: Path) -> None:
    """A ``config`` directory inside the project keeps its magic-value exemption."""
    project_root = _project_root_under(tmp_path / "tests")

    all_failed_names = _failed_check_names(
        project_root / "config" / "timing.py", PRODUCTION_CONTENT_WITH_MAGIC_VALUE
    )

    assert MAGIC_VALUE_CHECK_NAME not in all_failed_names, (
        f"an in-project config module must stay magic-value exempt, got {all_failed_names}"
    )


def test_should_walk_every_segment_for_a_target_with_no_project_root(
    tmp_path: Path,
) -> None:
    """An install-tree target outside every project keeps the whole-path walk."""
    install_target = tmp_path / ".claude" / "hooks" / "blocking" / "gate.py"
    staging_directory = tmp_path / "staging"
    staging_directory.mkdir()

    staged_relative = _staged_relative_path(staging_directory, install_target)

    assert staged_relative == ".claude/hooks/blocking/gate.py", (
        f"a target with no project root must keep its exemption tail, got {staged_relative}"
    )
