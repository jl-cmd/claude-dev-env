"""Tests for check_bugbot_ci silent-pass detection.

Covers:
- is_bugbot_run_clean returns True for completed success / completed neutral
- is_bugbot_run_clean returns False for completed failure, in_progress, missing
- is_bugbot_run_clean returns None when the gh CLI fails
- main(--check-clean) returns 0 on clean, 1 on not-clean, and
  EXIT_CODE_GH_ERROR on gh CLI failure (with stderr diagnostics)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent


@pytest.fixture(scope="session")
def check_bugbot_ci_module() -> Iterator[ModuleType]:
    """Load check_bugbot_ci with full sys.path and sys.modules isolation.

    Snapshots sys.path and sys.modules at session start; restores both
    unconditionally at session teardown so sibling tests inherit a clean
    loading environment. The production script performs its own
    membership-guarded sys.path.insert during exec_module so its config
    dependency resolves; that insert and any config.* modules it loads
    are reverted on teardown.
    """
    module_path = _SCRIPTS_DIRECTORY / "check_bugbot_ci.py"
    spec = importlib.util.spec_from_file_location("check_bugbot_ci", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys_path_snapshot = list(sys.path)
    sys_modules_snapshot = dict(sys.modules)
    evicted_config_modules = {
        each_module_name: sys.modules.pop(each_module_name)
        for each_module_name in list(sys.modules)
        if each_module_name == "config" or each_module_name.startswith("config.")
    }
    sys_modules_snapshot.update(evicted_config_modules)
    spec.loader.exec_module(module)
    try:
        yield module
    finally:
        sys.path[:] = sys_path_snapshot
        for each_new_module_name in list(sys.modules):
            if each_new_module_name not in sys_modules_snapshot:
                del sys.modules[each_new_module_name]
        for each_module_name, each_module_value in sys_modules_snapshot.items():
            sys.modules[each_module_name] = each_module_value


def _make_completed_process(
    stdout: str, returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.stderr = ""
    process.returncode = returncode
    return process


def _build_stdout(*all_check_entries: dict[str, object]) -> str:
    return "\n".join(json.dumps(each_entry) for each_entry in all_check_entries) + "\n"


def test_should_return_true_when_bugbot_completed_with_success_conclusion(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "success"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is True


def test_should_return_true_when_bugbot_completed_with_neutral_conclusion(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "bugbot", "status": "completed", "conclusion": "neutral"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is True


def test_should_return_false_when_bugbot_completed_with_failure_conclusion(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "failure"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_false_when_bugbot_still_in_progress(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "in_progress", "conclusion": None}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_false_when_no_bugbot_check_run_present(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "ci-other", "status": "completed", "conclusion": "success"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_false_when_first_bugbot_run_is_in_progress_even_if_later_one_clean(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "in_progress", "conclusion": None},
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "success"},
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_false_when_first_bugbot_run_failed_even_if_later_one_clean(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "failure"},
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "success"},
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_none_when_gh_cli_fails(
    check_bugbot_ci_module: ModuleType,
) -> None:
    failing_process = MagicMock(spec=subprocess.CompletedProcess)
    failing_process.stdout = ""
    failing_process.stderr = "boom"
    failing_process.returncode = 1
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=failing_process,
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is None


def test_main_check_clean_should_return_gh_error_code_when_gh_cli_fails(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing_process = MagicMock(spec=subprocess.CompletedProcess)
    failing_process.stdout = ""
    failing_process.stderr = "boom"
    failing_process.returncode = 1
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=failing_process,
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-clean", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == check_bugbot_ci_module.EXIT_CODE_GH_ERROR
    captured = capsys.readouterr()
    assert "gh api error: boom" in captured.err


def test_main_check_clean_should_return_zero_when_bugbot_clean(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "success"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-clean", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "not clean" not in captured.out


def test_main_check_clean_should_return_one_when_bugbot_not_clean(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "failure"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-clean", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not clean" in captured.out


def test_main_check_active_should_return_zero_when_bugbot_in_progress(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "in_progress", "conclusion": None}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-active", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == 0


def test_main_should_reject_check_clean_and_check_active_together(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        check_bugbot_ci_module.main(
            [
                "--check-clean",
                "--check-active",
                "--owner",
                "acme",
                "--repo",
                "repo",
                "--sha",
                "abc",
            ]
        )
    captured = capsys.readouterr()
    assert "not allowed with" in captured.err or "mutually exclusive" in captured.err
