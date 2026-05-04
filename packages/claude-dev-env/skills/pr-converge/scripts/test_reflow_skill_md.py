"""Tests for reflow_skill_md."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "reflow_skill_md.py"
    spec = importlib.util.spec_from_file_location("reflow_skill_md", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reflow_skill_md_module = _load_module()


def test_should_preserve_pr_converge_state_json_path_in_yaml_description() -> None:
    lines = [
        "  Multi-PR runs persist traffic in",
        "  `<TMPDIR>/pr-converge-<session_id>/state.json` per Multi-PR",
        "  orchestration model.",
        "---",
    ]
    all_reflowed_lines, next_index = reflow_skill_md_module.reflow_yaml_description_block(
        lines, 0
    )
    reflowed_description = " ".join(each_line.strip() for each_line in all_reflowed_lines)

    assert next_index == len(lines)
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json`" in reflowed_description
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json>`" not in reflowed_description
