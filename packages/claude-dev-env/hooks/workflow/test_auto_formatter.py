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

import pytest

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "auto_formatter.py")
HOOKS_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "hooks", "hooks.json"
)
POST_TOOL_USE_DISPATCHER_COMMAND_FRAGMENT = "validation/post_tool_use_dispatcher.py"
UNUSED_IMPORT_SOURCE = "import os\n\n\nVALUE = 1\n"
HOOK_RUN_TIMEOUT_SECONDS = 60


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
    subprocess.run(["git", "init"], cwd=repository_path, capture_output=True, check=True)
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


def _load_auto_formatter_module() -> object:
    module_spec = importlib.util.spec_from_file_location("auto_formatter", HOOK_SCRIPT_PATH)
    assert module_spec is not None and module_spec.loader is not None
    auto_formatter_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(auto_formatter_module)
    return auto_formatter_module


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
