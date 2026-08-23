"""Tests for the auto_formatter hook.

Exercises the real hook against real ruff inside a real git repository. A
brand-new (untracked) Python file carrying an unused import is fixed in
place, while the same file arriving through the Edit tool is left untouched
so the fix stays scoped to newly created files.

The sandbox is rooted under the user's home directory via ``tempfile.mkdtemp``
rather than the OS temp directory, matching the sibling workflow-hook tests.
"""

import contextlib
import functools
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "auto_formatter.py")
HOOKS_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "hooks", "hooks.json"
)
POST_TOOL_USE_DISPATCHER_COMMAND_FRAGMENT = "validation/post_tool_use_dispatcher.py"
UNUSED_IMPORT_SOURCE = "import os\n\n\nVALUE = 1\n"
HOOK_RUN_TIMEOUT_SECONDS = 60


def build_fixture_git_environment() -> dict[str, str]:
    return {
        each_name: each_value
        for each_name, each_value in os.environ.items()
        if not each_name.upper().startswith("GIT_")
    }


def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


def _force_rmtree(target_path: str) -> None:
    handler_kw = (
        {"onexc": _strip_read_only_and_retry}
        if sys.version_info >= (3, 12)
        else {"onerror": _strip_read_only_and_retry}
    )
    with contextlib.suppress(OSError):
        shutil.rmtree(target_path, **handler_kw)


@functools.lru_cache(maxsize=1)
def _get_sandbox_parent_directory() -> str:
    return tempfile.mkdtemp(prefix="pytest_auto_formatter_", dir=str(Path.home()))


@pytest.fixture(scope="session", autouse=True)
def _cleanup_sandbox_parent_directory() -> Generator[None]:
    yield
    if _get_sandbox_parent_directory.cache_info().currsize:
        _force_rmtree(_get_sandbox_parent_directory())
        _get_sandbox_parent_directory.cache_clear()


@pytest.fixture
def git_repository() -> Generator[Path]:
    repository_path = Path(tempfile.mkdtemp(dir=_get_sandbox_parent_directory()))
    subprocess.run(
        ["git", "init"],
        cwd=repository_path,
        capture_output=True,
        check=True,
        env=build_fixture_git_environment(),
    )
    yield repository_path
    _force_rmtree(str(repository_path))


def _run_hook(tool_name: str, file_path: Path) -> subprocess.CompletedProcess[str]:
    hook_input = json.dumps({"tool_name": tool_name, "tool_input": {"file_path": str(file_path)}})
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input,
        capture_output=True,
        text=True,
        timeout=HOOK_RUN_TIMEOUT_SECONDS,
        check=False,
        env=build_fixture_git_environment(),
    )


class TestRuffFixOnNewFiles:
    def should_remove_unused_import_from_new_untracked_python_file(
        self, git_repository: Path
    ) -> None:
        new_file = git_repository / "brand_new.py"
        new_file.write_text(UNUSED_IMPORT_SOURCE, encoding="utf-8")

        completed_hook = _run_hook("Write", new_file)

        assert completed_hook.returncode == 0
        assert "import os" not in new_file.read_text(encoding="utf-8")

    def should_leave_file_arriving_through_edit_untouched(self, git_repository: Path) -> None:
        edited_file = git_repository / "edited.py"
        edited_file.write_text(UNUSED_IMPORT_SOURCE, encoding="utf-8")

        completed_hook = _run_hook("Edit", edited_file)

        assert completed_hook.returncode == 0
        assert "import os" in edited_file.read_text(encoding="utf-8")

    def should_leave_tracked_python_file_arriving_through_write_untouched(
        self, git_repository: Path
    ) -> None:
        tracked_file = git_repository / "tracked.py"
        tracked_file.write_text(UNUSED_IMPORT_SOURCE, encoding="utf-8")
        subprocess.run(
            ["git", "add", "tracked.py"],
            cwd=git_repository,
            capture_output=True,
            check=True,
            env=build_fixture_git_environment(),
        )

        completed_hook = _run_hook("Write", tracked_file)

        assert completed_hook.returncode == 0
        assert "import os" in tracked_file.read_text(encoding="utf-8")


def test_tracked_write_leaves_unused_import_in_place(git_repository: Path) -> None:
    tracked_file = git_repository / "tracked_module.py"
    tracked_file.write_text(UNUSED_IMPORT_SOURCE, encoding="utf-8")
    subprocess.run(
        ["git", "add", "tracked_module.py"],
        cwd=git_repository,
        capture_output=True,
        check=True,
        env=build_fixture_git_environment(),
    )

    completed_hook = _run_hook("Write", tracked_file)

    assert completed_hook.returncode == 0
    assert "import os" in tracked_file.read_text(encoding="utf-8")


def _load_auto_formatter_module() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location("auto_formatter", HOOK_SCRIPT_PATH)
    assert module_spec is not None and module_spec.loader is not None
    auto_formatter_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(auto_formatter_module)
    return auto_formatter_module


def test_formatter_eligibility_requires_write_tool_and_untracked_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auto_formatter_module = _load_auto_formatter_module()
    source_file = tmp_path / "new_module.py"
    monkeypatch.setattr(auto_formatter_module, "is_untracked_in_git", lambda _: True)

    assert auto_formatter_module.is_formatter_eligible("Write", str(source_file))
    assert not auto_formatter_module.is_formatter_eligible("Bash", str(source_file))


def test_formatter_eligibility_protects_hook_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auto_formatter_module = _load_auto_formatter_module()
    hooks_directory = tmp_path / "hooks"
    protected_file = hooks_directory / "generated.py"
    monkeypatch.setattr(
        auto_formatter_module,
        "HOOKS_DIR",
        f"{hooks_directory}{os.sep}",
    )

    assert auto_formatter_module.is_protected_path(str(protected_file))


def test_formatter_eligibility_protects_symlinked_hook_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auto_formatter_module = _load_auto_formatter_module()
    hooks_directory = tmp_path / "hooks"
    hooks_directory.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.write_text(UNUSED_IMPORT_SOURCE, encoding="utf-8")
    symlinked_file = hooks_directory / "linked.py"
    try:
        symlinked_file.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        return
    monkeypatch.setattr(
        auto_formatter_module,
        "HOOKS_DIR",
        f"{hooks_directory}{os.sep}",
    )
    monkeypatch.setattr(auto_formatter_module, "is_untracked_in_git", lambda _: True)

    assert auto_formatter_module.is_formatter_eligible("Write", str(symlinked_file)) is False


def test_formatter_diagnostic_stays_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    auto_formatter_module = _load_auto_formatter_module()

    def return_formatter_failure(
        command: list[str], **_options: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            3,
            "formatter stdout",
            "formatter stderr",
        )

    monkeypatch.setattr(subprocess, "run", return_formatter_failure)
    auto_formatter_module.run_eligible_formatter("broken.py")

    captured_output = capsys.readouterr()
    assert "formatter stdout" in captured_output.err
    assert "formatter stderr" in captured_output.err
    assert captured_output.out == ""


def test_tracked_write_ignores_redirected_git_dir(
    git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tracked_file = git_repository / "redirected_git_dir.py"
    tracked_file.write_text(UNUSED_IMPORT_SOURCE, encoding="utf-8")
    subprocess.run(
        ["git", "add", "redirected_git_dir.py"],
        cwd=git_repository,
        capture_output=True,
        check=True,
        env=build_fixture_git_environment(),
    )
    redirected_repository = tmp_path / "redirected_repository"
    redirected_repository.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=redirected_repository,
        capture_output=True,
        check=True,
        env=build_fixture_git_environment(),
    )
    monkeypatch.setenv("GIT_DIR", str(redirected_repository / ".git"))

    completed_hook = _run_hook("Write", tracked_file)

    assert completed_hook.returncode == 0
    assert "import os" in tracked_file.read_text(encoding="utf-8")


def test_python_formatting_preserves_crlf_line_endings(git_repository: Path) -> None:
    source_file = git_repository / "crlf_module.py"
    source_file.write_bytes(b"x=1\r\ny  =  2\r\n")

    completed_hook = _run_hook("Write", source_file)

    assert completed_hook.returncode == 0
    formatted_source = source_file.read_bytes()
    assert b"\r\n" in formatted_source
    assert b"\n" not in formatted_source.replace(b"\r\n", b"")


def _registered_auto_formatter_timeout() -> int:
    with open(HOOKS_JSON_PATH, encoding="utf-8") as hooks_file:
        hooks_configuration = json.load(hooks_file)
    for each_event in hooks_configuration["hooks"].values():
        for each_matcher in each_event:
            for each_hook in each_matcher["hooks"]:
                if POST_TOOL_USE_DISPATCHER_COMMAND_FRAGMENT in each_hook["command"]:
                    return int(each_hook["timeout"])
    raise AssertionError(
        "post_tool_use_dispatcher (which hosts auto_formatter) is not registered in hooks.json"
    )


class TestPythonFormatTimeoutBudget:
    def should_keep_both_sequential_python_subprocesses_under_the_harness_budget(self) -> None:
        auto_formatter_module = _load_auto_formatter_module()
        budgeted_total = auto_formatter_module.budgeted_python_format_seconds()

        assert budgeted_total < _registered_auto_formatter_timeout()
