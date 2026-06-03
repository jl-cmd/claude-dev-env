"""Shared subprocess-invocation helpers for the md_to_html_blocker test suites.

Subprocess CWD is rooted in a per-session sandbox created lazily so that
relative-path test cases canonicalize outside any `.claude-plugin/` ancestor,
outside the OS temp directory, and outside the exempt home-relative
subdirectories. The sandbox is a real repo root (it carries a `.git` marker) so
relative `README.md` / `CHANGELOG.md` writes exercise the repo-root exemption
path. This keeps the suites independent of where pytest itself is run.
"""

import functools
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "md_to_html_blocker.py")


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
    try:
        shutil.rmtree(target_path, **handler_kw)
    except OSError:
        pass


@functools.lru_cache(maxsize=1)
def _get_sandbox_parent_directory() -> str:
    sandbox_parent = tempfile.mkdtemp(prefix="pytest_md_blocker_", dir=str(Path.home()))
    git_marker_path = os.path.join(sandbox_parent, ".git")
    Path(git_marker_path).touch()
    return sandbox_parent


class _RunHook:
    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            cwd=_get_sandbox_parent_directory(),
        )


_run_hook = _RunHook()
