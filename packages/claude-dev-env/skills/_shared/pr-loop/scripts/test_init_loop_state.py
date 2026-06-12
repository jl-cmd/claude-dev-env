"""Tests for init_loop_state.create_loop_state consuming the typed workspace."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_init_loop_state_module() -> ModuleType:
    module_path = _SCRIPTS_DIR / "init_loop_state.py"
    spec = importlib.util.spec_from_file_location("init_loop_state", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


init_loop_state = _load_init_loop_state_module()


def test_create_loop_state_writes_state_under_typed_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create_loop_state resolves the worktree from PerPrWorkspace.worktree and
    writes loop-state.json inside it, with the starting SHA recorded."""
    path_resolver_module = init_loop_state.resolve_run_temp_dir.__globals__["tempfile"]
    monkeypatch.setattr(path_resolver_module, "gettempdir", lambda: str(tmp_path))
    state_path = init_loop_state.create_loop_state(
        pr_number=422,
        head_ref="feat/branch",
        starting_sha="abc1234",
        is_multi_pr=False,
    )
    assert state_path.name == "loop-state.json"
    assert state_path.parent.name == "worktree"
    written_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert written_state["starting_sha"] == "abc1234"
    assert written_state["loop_count"] == 0


def test_main_prints_state_path_with_forward_slashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path_resolver_module = init_loop_state.resolve_run_temp_dir.__globals__["tempfile"]
    monkeypatch.setattr(path_resolver_module, "gettempdir", lambda: str(tmp_path))
    exit_code = init_loop_state.main(
        [
            "--pr-number",
            "422",
            "--head-ref",
            "feat/branch",
            "--starting-sha",
            "abc1234",
        ]
    )
    assert exit_code == 0
    printed_path = capsys.readouterr().out.strip()
    assert "\\" not in printed_path
    assert printed_path.endswith("worktree/loop-state.json")
