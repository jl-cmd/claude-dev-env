"""Meta-test: every blocking hook must call log_hook_block at its block site.

Discovers every .py under hooks/ whose source contains a block-emit pattern
(``"permissionDecision": "deny"`` or ``"decision": "block"``), excludes test
files and the logger module itself, then asserts each one imports and calls
``log_hook_block(``.
"""

from __future__ import annotations

import re
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent

_DENY_PATTERN = re.compile(r'"permissionDecision":\s*"deny"')
_BLOCK_PATTERN = re.compile(r'"decision":\s*"block"')
_LOG_CALL_PATTERN = re.compile(r"\blog_hook_block\(")

_LOGGER_MODULE_NAME = "hook_block_logger.py"


def _is_test_file(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def _discover_blocking_hook_paths() -> list[Path]:
    all_blocking_hook_paths: list[Path] = []
    for each_py_file in _HOOKS_ROOT.rglob("*.py"):
        if _is_test_file(each_py_file):
            continue
        if each_py_file.name == _LOGGER_MODULE_NAME:
            continue
        source = each_py_file.read_text(encoding="utf-8", errors="replace")
        if _DENY_PATTERN.search(source) or _BLOCK_PATTERN.search(source):
            all_blocking_hook_paths.append(each_py_file)
    return sorted(all_blocking_hook_paths)


def test_every_blocking_hook_calls_log_hook_block() -> None:
    all_blocking_hooks = _discover_blocking_hook_paths()
    assert all_blocking_hooks, "No blocking hooks discovered — check _HOOKS_ROOT path"

    all_uninstrumented_hooks: list[str] = []
    for each_hook_path in all_blocking_hooks:
        source = each_hook_path.read_text(encoding="utf-8", errors="replace")
        if not _LOG_CALL_PATTERN.search(source):
            all_uninstrumented_hooks.append(str(each_hook_path.relative_to(_HOOKS_ROOT)))

    assert not all_uninstrumented_hooks, (
        f"{len(all_uninstrumented_hooks)} blocking hook(s) missing log_hook_block call:\n"
        + "\n".join(f"  - {each_path}" for each_path in all_uninstrumented_hooks)
    )
