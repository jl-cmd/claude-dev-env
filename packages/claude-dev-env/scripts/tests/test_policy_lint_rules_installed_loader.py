"""Load terminology through the verified installed shared-tree resolver."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from policy_lint import adapters


def test_pr_loop_loader_uses_the_shared_tree_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_name = "policy_fixture_terminology"
    (tmp_path / f"{module_name}.py").write_text("IS_FIXTURE = True\n", encoding="utf-8")
    all_calls: list[tuple[object, ...]] = []

    def resolve_directory(*all_arguments: object) -> Path:
        all_calls.append(all_arguments)
        return tmp_path

    monkeypatch.setattr(adapters, "resolve_shared_scripts_directory", resolve_directory)
    monkeypatch.setattr(sys, "path", list(sys.path))
    loaded = adapters._pr_loop_script_module(module_name)
    assert loaded.IS_FIXTURE is True
    assert Path(loaded.__file__).parent == tmp_path
    assert all_calls[0][2:] == ("pr-loop", f"{module_name}.py", 2)
    monkeypatch.delitem(sys.modules, module_name)
