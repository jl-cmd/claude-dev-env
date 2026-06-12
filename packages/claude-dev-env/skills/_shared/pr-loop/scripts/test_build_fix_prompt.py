"""Tests for build_fix_prompt's agent-facing path rendering."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_build_fix_prompt() -> ModuleType:
    module_path = _SCRIPTS_DIR / "build_fix_prompt.py"
    spec = importlib.util.spec_from_file_location("build_fix_prompt", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_fix_prompt"] = module
    spec.loader.exec_module(module)
    return module


build_fix_prompt = _load_build_fix_prompt()


def test_context_worktree_path_renders_with_forward_slashes(tmp_path: Path) -> None:
    findings_json_path = tmp_path / "findings.json"
    findings_json_path.write_text(
        json.dumps([{"severity": "P1", "file": "a.py", "line": 1}]),
        encoding="utf-8",
    )
    root = build_fix_prompt.build_fix_prompt_xml(
        owner="jl-cmd",
        repo="claude-code-config",
        pr_number=376,
        loop=1,
        head_ref="feat/branch",
        base_ref="main",
        worktree_path=Path("C:/Users/jon/AppData/Local/Temp/bugteam-pr-376/worktree"),
        findings_json_path=findings_json_path,
    )
    context = root.find("context")
    assert context is not None
    worktree_text = context.findtext("worktree_path")
    assert worktree_text == "C:/Users/jon/AppData/Local/Temp/bugteam-pr-376/worktree"
