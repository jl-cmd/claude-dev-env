"""Behavioral tests for the staged_test_running parts module."""

import subprocess
from pathlib import Path

import pytest

from code_rules_gate_parts import git_file_sets, staged_pytest_entry, staged_test_running
from pr_loop_shared_constants.code_rules_gate_constants import (
    CODE_RULES_GATE_PYTHONPATH_ENV_VAR,
    PYTHONPATH_ENV_VAR,
)


def _git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env=git_file_sets.repository_environment(),
    )


def _init_repository(repository_root: Path) -> None:
    _git(repository_root, "init", "--initial-branch=main")
    _git(repository_root, "config", "user.email", "test@example.com")
    _git(repository_root, "config", "user.name", "Test")
    _git(repository_root, "config", "commit.gpgsign", "false")
    (repository_root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repository_root, "add", "-A")
    _git(repository_root, "commit", "-m", "seed")


def _write_and_stage(repository_root: Path, relative_path: str, file_text: str) -> Path:
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(file_text, encoding="utf-8")
    _git(repository_root, "add", "--", relative_path)
    return file_path


def _repository_with_root_pytest_config(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    return repository_root


def test_run_staged_test_files_returns_zero_when_nothing_staged(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_batched_pytest_arguments_splits_over_the_budget() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["aaaa", "bbbb", "cccc"], 10)
    assert all_batches == [["aaaa", "bbbb"], ["cccc"]]


def test_batched_pytest_arguments_keeps_oversized_argument_in_its_own_batch() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["wide_argument"], 4)
    assert all_batches == [["wide_argument"]]


def test_run_staged_test_files_returns_zero_when_only_multiple_confests_staged(
    tmp_path: Path,
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    _write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    _write_and_stage(
        repository_root, "pkg_c/tests/conftest.py", "import pytest\n"
    )

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_passes_when_confests_stage_with_passing_test(
    tmp_path: Path,
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    _write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    _write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_passes() -> None:\n    assert True\n",
    )

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_fails_when_real_test_fails_alongside_confests(
    tmp_path: Path,
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    _write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    _write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_running.run_staged_test_files(repository_root) != 0


def test_staged_failing_test_cannot_pass_from_an_unstaged_repair(tmp_path: Path) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    test_path = _write_and_stage(
        repository_root,
        "test_staged.py",
        "def test_staged_failure() -> None:\n    assert False\n",
    )
    test_path.write_text(
        "def test_staged_failure() -> None:\n    assert True\n", encoding="utf-8"
    )

    assert staged_test_running.run_staged_test_files(repository_root) != 0


def test_staged_failing_production_cannot_pass_from_an_unstaged_repair(tmp_path: Path) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    production_path = _write_and_stage(
        repository_root,
        "feature.py",
        "def is_ready() -> bool:\n    return False\n",
    )
    _write_and_stage(
        repository_root,
        "test_feature.py",
        "from feature import is_ready\n\n\ndef test_feature_is_ready() -> None:\n    assert is_ready()\n",
    )
    production_path.write_text(
        "def is_ready() -> bool:\n    return True\n", encoding="utf-8"
    )

    assert staged_test_running.run_staged_test_files(repository_root) != 0


def test_staged_pytest_config_owns_group_after_unstaged_config_removal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    _write_and_stage(repository_root, "failing_skill/pytest.ini", "[pytest]\n")
    _write_and_stage(
        repository_root,
        "failing_skill/test_feature.py",
        "def test_feature_fails() -> None:\n    assert False\n",
    )
    (repository_root / "failing_skill" / "pytest.ini").unlink()

    assert staged_test_running.run_staged_test_files(repository_root) != 0
    captured = capsys.readouterr()
    assert "failing_skill" in captured.err


@pytest.mark.parametrize(
    "pythonpath_variable",
    [CODE_RULES_GATE_PYTHONPATH_ENV_VAR, PYTHONPATH_ENV_VAR],
)
def test_live_pythonpath_cannot_hide_staged_production_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pythonpath_variable: str,
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    production_path = _write_and_stage(
        repository_root,
        "feature.py",
        "def is_ready() -> bool:\n    return False\n",
    )
    _write_and_stage(
        repository_root,
        "test_feature.py",
        "from feature import is_ready\n\n\ndef test_feature_is_ready() -> None:\n    assert is_ready()\n",
    )
    production_path.write_text(
        "def is_ready() -> bool:\n    return True\n", encoding="utf-8"
    )
    monkeypatch.setenv(pythonpath_variable, str(repository_root))

    assert staged_test_running.run_staged_test_files(repository_root) != 0


def test_editable_finder_mapping_moves_live_source_to_snapshot(tmp_path: Path) -> None:
    original_root = tmp_path / "original"
    snapshot_root = tmp_path / "snapshot"

    class EditableFinder:
        MAPPING = {"feature": str(original_root / "src" / "feature")}

    finder = EditableFinder()
    original_meta_path = list(staged_pytest_entry.sys.meta_path)
    staged_pytest_entry.sys.meta_path.insert(0, finder)
    try:
        staged_pytest_entry._rewrite_editable_finder_mappings(
            original_root, snapshot_root
        )
    finally:
        staged_pytest_entry.sys.meta_path[:] = original_meta_path

    assert finder.MAPPING["feature"] == str(snapshot_root / "src" / "feature")


def test_staged_pytest_sees_cached_diff_against_head(tmp_path: Path) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(
        repository_root,
        "test_cached_surface.py",
        """import subprocess


def test_cached_surface_contains_this_test() -> None:
    completed = subprocess.run(
        [\"git\", \"diff\", \"--cached\", \"HEAD\", \"--name-only\"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert \"test_cached_surface.py\" in completed.stdout
""",
    )

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_skip_worktree_staged_test_is_materialized(tmp_path: Path) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(
        repository_root,
        "test_skip_worktree.py",
        "def test_staged_failure_is_collected() -> None:\n    assert False\n",
    )
    _git(repository_root, "update-index", "--skip-worktree", "test_skip_worktree.py")

    assert staged_test_running.run_staged_test_files(repository_root) != 0


def test_non_test_staged_surface_skips_snapshot_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(repository_root, "feature.py", "IS_READY = True\n")
    all_calls: list[Path] = []

    def record_snapshot(*arguments) -> bool:
        all_calls.append(arguments[1])
        return True

    monkeypatch.setattr(staged_test_running, "_create_snapshot_worktree", record_snapshot)

    assert staged_test_running.run_staged_test_files(repository_root) == 0
    assert all_calls == []


def test_inherited_git_environment_cannot_redirect_staged_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    victim_root = tmp_path / "victim"
    victim_root.mkdir()
    _init_repository(victim_root)
    _write_and_stage(
        repository_root,
        "test_target.py",
        "def test_target_failure() -> None:\n    assert False\n",
    )
    monkeypatch.setenv("GIT_DIR", str(victim_root / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(victim_root))
    monkeypatch.setenv("GIT_INDEX_FILE", str(victim_root / ".git" / "index"))

    assert staged_test_running.run_staged_test_files(repository_root) != 0
