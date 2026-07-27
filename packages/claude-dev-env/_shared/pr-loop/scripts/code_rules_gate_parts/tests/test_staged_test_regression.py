"""Behavioral tests for the staged_test_regression parts module.

Every test drives a real git repository and a real pytest subprocess — no
mocked git state, no mocked pytest run — the same shape the live commit gate
exercises.
"""

from pathlib import Path

import pytest

from code_rules_gate_parts import baseline_import_isolation, staged_test_regression
from code_rules_gate_parts.tests._repo_test_helpers import (
    init_repository,
    repository_root_without_pytest_config,
    repository_with_root_pytest_config,
    run_git,
    write_and_stage,
    write_commit_and_stage_change,
)

UNREACHABLE_PROBE_TIMEOUT_SECONDS = 0.001

CONSUMER_TEST_TEXT = (
    "import foo\n\n\ndef test_consumer_reads_head_value() -> None:\n"
    "    assert foo.VALUE == 'clean', foo.__file__\n"
)

CONSUMER_TEST_TEXT_WITH_STAGED_EDIT = CONSUMER_TEST_TEXT + (
    "\n\ndef test_consumer_extra() -> None:\n    assert True\n"
)

IMPORT_HOOK_SITECUSTOMIZE_TEMPLATE = (
    "import sys\n"
    "from importlib.machinery import PathFinder\n\n"
    "PINNED_ROOT = r'{pinned_root}'\n\n\n"
    "class PinnedFinder(PathFinder):\n"
    "    @classmethod\n"
    "    def find_spec(cls, fullname, path=None, target=None):\n"
    "        if fullname.split('.')[0] != 'foo':\n"
    "            return None\n"
    "        return super().find_spec(fullname, [PINNED_ROOT], target)\n\n\n"
    "sys.meta_path.insert(0, PinnedFinder)\n"
)


def stage_a_change_that_breaks_a_consumer(repository_root: Path) -> None:
    """Commit a passing consumer of ``foo``, then stage a ``foo`` edit that breaks it.

    The consumer imports ``foo`` by name, so which copy of ``foo`` the baseline
    run loads decides whether the gate sees a regression at all.
    """
    write_and_stage(repository_root, "packages/foo/__init__.py", "VALUE = 'clean'\n")
    write_and_stage(repository_root, "pkg_a/test_alpha.py", CONSUMER_TEST_TEXT)
    run_git(repository_root, "commit", "--no-verify", "-m", "seed consumer")
    write_and_stage(repository_root, "packages/foo/__init__.py", "VALUE = 'dirty'\n")
    write_and_stage(
        repository_root, "pkg_a/test_alpha.py", CONSUMER_TEST_TEXT_WITH_STAGED_EDIT
    )


def test_pythonpath_route_into_the_working_tree_does_not_hide_a_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    stage_a_change_that_breaks_a_consumer(repository_root)
    monkeypatch.setenv("PYTHONPATH", str(repository_root / "packages"))

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_a_probe_that_runs_out_of_time_still_reaches_a_gate_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert True\n"
        ),
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert 1 == 1\n"
        ),
    )
    monkeypatch.setattr(
        baseline_import_isolation,
        "BASELINE_IMPORT_PROBE_TIMEOUT_SECONDS",
        UNREACHABLE_PROBE_TIMEOUT_SECONDS,
    )

    exit_code = staged_test_regression.run_staged_test_files(repository_root)

    assert exit_code == 0
    assert "import-root probe" in capsys.readouterr().err


def test_import_hook_route_into_the_working_tree_is_reported_and_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    stage_a_change_that_breaks_a_consumer(repository_root)
    import_hook_directory = tmp_path / "import_hook"
    import_hook_directory.mkdir()
    (import_hook_directory / "sitecustomize.py").write_text(
        IMPORT_HOOK_SITECUSTOMIZE_TEMPLATE.format(pinned_root=repository_root / "packages"),
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(import_hook_directory))

    exit_code = staged_test_regression.run_staged_test_files(repository_root)

    assert exit_code != 0
    assert "imported 1 module(s) from your working tree" in capsys.readouterr().err


def test_pre_existing_failure_does_not_block_an_unrelated_staged_change(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert True\n"
        ),
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert 1 == 1\n"
        ),
    )

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_staged_change_that_newly_breaks_a_passing_test_blocks(tmp_path: Path) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_passes() -> None:\n    assert True\n",
        "def test_alpha_passes() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_brand_new_failing_test_with_no_baseline_blocks(tmp_path: Path) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_mixed_group_blocks_only_on_the_newly_broken_test(tmp_path: Path) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        (
            "def test_already_red() -> None:\n    assert False\n"
            "def test_stays_green() -> None:\n    assert True\n"
        ),
        (
            "def test_already_red() -> None:\n    assert False\n"
            "def test_stays_green() -> None:\n    assert False\n"
        ),
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_regression_gate_leaves_the_staged_index_and_worktree_list_alone(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert True\n"
        ),
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert 1 == 1\n"
        ),
    )

    staged_test_regression.run_staged_test_files(repository_root)

    staged_content = run_git(
        repository_root, "show", ":pkg_a/test_alpha.py"
    ).stdout.decode("utf-8")
    assert "assert 1 == 1" in staged_content
    status = run_git(repository_root, "status", "--porcelain").stdout.decode("utf-8")
    assert "M  pkg_a/test_alpha.py" in status
    worktree_list = run_git(
        repository_root, "worktree", "list", "--porcelain"
    ).stdout.decode("utf-8")
    assert worktree_list.count("worktree ") == 1
    assert "code_rules_gate_baseline_" not in worktree_list


def test_run_staged_test_files_returns_zero_when_nothing_staged(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    init_repository(repository_root)

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_returns_zero_when_only_multiple_confests_staged(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_c/tests/conftest.py", "import pytest\n")

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_passes_when_confests_stage_with_passing_test(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_passes() -> None:\n    assert True\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_fails_when_real_test_fails_alongside_confests(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_no_head_baseline_blocks_on_any_staged_failure(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    run_git(repository_root, "init", "--initial-branch=main")
    run_git(repository_root, "config", "user.email", "test@example.com")
    run_git(repository_root, "config", "user.name", "Test")
    run_git(repository_root, "config", "commit.gpgsign", "false")
    write_and_stage(repository_root, "pytest.ini", "[pytest]\n")
    write_and_stage(
        repository_root,
        "test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def _stage_package_owning_a_bare_config(
    repository_root: Path, package_name: str, marker_value: str
) -> None:
    """Stage a config-less top-level package whose tests import a bare ``config``.

    Two such packages staged together reproduce the measured collision: one
    pytest session binds ``config`` to whichever package imports first, so the
    other package's test reads the wrong marker.
    """
    write_and_stage(
        repository_root,
        f"{package_name}/config/__init__.py",
        f'PACKAGE_MARKER = "{marker_value}"\n',
    )
    write_and_stage(
        repository_root,
        f"{package_name}/test_{package_name}.py",
        "from config import PACKAGE_MARKER\n\n\n"
        f"def test_{package_name}_reads_its_own_config() -> None:\n"
        f'    assert PACKAGE_MARKER == "{marker_value}"\n',
    )


def test_run_staged_test_files_passes_when_config_less_packages_share_a_module_name(
    tmp_path: Path,
) -> None:
    repository_root = repository_root_without_pytest_config(tmp_path)
    init_repository(repository_root)
    _stage_package_owning_a_bare_config(repository_root, "alpha_package", "alpha")
    _stage_package_owning_a_bare_config(repository_root, "beta_package", "beta")

    assert staged_test_regression.run_staged_test_files(repository_root) == 0
