"""Tests for build_fix_prompt's agent-facing path rendering."""

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

from skills_pr_loop_constants.path_resolver_constants import (
    FIX_COMMENT_POSTING_AGENT_TEXT,
    FIX_COMMENT_POSTING_HEADLESS_TEXT,
    FIX_OUTCOME_XML_TEMPLATE,
    FIX_OUTPUT_FORMAT_AGENT_TEXT,
    FIX_OUTPUT_FORMAT_HEADLESS_TEMPLATE,
    FIX_PROMPT_FLAVOR_AGENT,
    FIX_PROMPT_FLAVOR_HEADLESS,
)


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


def _write_findings_json(tmp_path: Path) -> Path:
    findings_json_path = tmp_path / "findings.json"
    findings_json_path.write_text(
        json.dumps([{"severity": "P1", "file": "a.py", "line": 1}]),
        encoding="utf-8",
    )
    return findings_json_path


def test_context_worktree_path_renders_with_forward_slashes(tmp_path: Path) -> None:
    findings_json_path = _write_findings_json(tmp_path)
    root = build_fix_prompt.build_fix_prompt_xml(
        owner="jl-cmd",
        repo="claude-dev-env",
        pr_number=376,
        loop=1,
        head_ref="feat/branch",
        base_ref="main",
        worktree_path=Path("C:/Users/example/AppData/Local/Temp/bugteam-pr-376/worktree"),
        findings_json_path=findings_json_path,
    )
    context = root.find("context")
    assert context is not None
    worktree_text = context.findtext("worktree_path")
    assert worktree_text == "C:/Users/example/AppData/Local/Temp/bugteam-pr-376/worktree"


def test_emit_fix_prompt_returns_xml_string_with_worktree_path(tmp_path: Path) -> None:
    findings_json_path = _write_findings_json(tmp_path)
    worktree_path = Path("C:/Users/example/AppData/Local/Temp/bugteam-pr-376/worktree")
    xml_text = build_fix_prompt.emit_fix_prompt(
        owner="jl-cmd",
        repo="claude-dev-env",
        pr_number=376,
        loop=1,
        head_ref="feat/branch",
        base_ref="main",
        worktree_path=worktree_path,
        findings_json_path=findings_json_path,
    )
    assert isinstance(xml_text, str)
    assert "C:/Users/example/AppData/Local/Temp/bugteam-pr-376/worktree" in xml_text
    assert 'role="fix"' in xml_text
    assert "<spawn_prompt" in xml_text


def test_parse_arguments_defaults_flavor_to_agent() -> None:
    arguments = build_fix_prompt.parse_arguments([
        "--owner", "jl-cmd",
        "--repo", "claude-dev-env",
        "--pr-number", "422",
        "--loop", "1",
        "--head-ref", "feat/branch",
        "--base-ref", "main",
        "--worktree-path", "/tmp/wt",
        "--findings-json", "/tmp/findings.json",
    ])
    assert arguments.flavor == FIX_PROMPT_FLAVOR_AGENT


def test_parse_arguments_reads_headless_flavor() -> None:
    arguments = build_fix_prompt.parse_arguments([
        "--owner", "jl-cmd",
        "--repo", "claude-dev-env",
        "--pr-number", "422",
        "--loop", "1",
        "--head-ref", "feat/branch",
        "--base-ref", "main",
        "--worktree-path", "/tmp/wt",
        "--findings-json", "/tmp/findings.json",
        "--flavor", FIX_PROMPT_FLAVOR_HEADLESS,
    ])
    assert arguments.flavor == FIX_PROMPT_FLAVOR_HEADLESS


def test_agent_flavor_comment_posting_and_output_format(tmp_path: Path) -> None:
    findings_json_path = _write_findings_json(tmp_path)
    root = build_fix_prompt.build_fix_prompt_xml(
        owner="jl-cmd",
        repo="claude-dev-env",
        pr_number=422,
        loop=1,
        head_ref="feat/branch",
        base_ref="main",
        worktree_path=Path("/tmp/bugteam-pr-422/worktree"),
        findings_json_path=findings_json_path,
        flavor=FIX_PROMPT_FLAVOR_AGENT,
    )
    comment_posting = root.find("comment_posting")
    assert comment_posting is not None
    assert comment_posting.text == FIX_COMMENT_POSTING_AGENT_TEXT
    output_format = root.find("output_format")
    assert output_format is not None
    assert output_format.text == FIX_OUTPUT_FORMAT_AGENT_TEXT
    execution = root.find("execution")
    assert execution is not None
    all_step_texts = [each_step.text or "" for each_step in execution]
    assert any("commit" in each_step.lower() for each_step in all_step_texts)
    assert any("push" in each_step.lower() for each_step in all_step_texts)


def test_headless_flavor_forbids_commit_push_and_mcp(tmp_path: Path) -> None:
    findings_json_path = _write_findings_json(tmp_path)
    worktree_path = Path("/tmp/bugteam-pr-422/worktree")
    pr_number = 422
    loop = 3
    root = build_fix_prompt.build_fix_prompt_xml(
        owner="jl-cmd",
        repo="claude-dev-env",
        pr_number=pr_number,
        loop=loop,
        head_ref="feat/branch",
        base_ref="main",
        worktree_path=worktree_path,
        findings_json_path=findings_json_path,
        flavor=FIX_PROMPT_FLAVOR_HEADLESS,
    )
    comment_posting = root.find("comment_posting")
    assert comment_posting is not None
    assert comment_posting.text == FIX_COMMENT_POSTING_HEADLESS_TEXT
    assert "MCP" not in (comment_posting.text or "")
    assert "TaskCreate" not in (comment_posting.text or "")
    assert "gh" in (comment_posting.text or "")

    expected_outcome_path = (
        worktree_path
        / FIX_OUTCOME_XML_TEMPLATE.format(number=pr_number, loop=loop)
    ).as_posix()
    output_format = root.find("output_format")
    assert output_format is not None
    assert output_format.text == FIX_OUTPUT_FORMAT_HEADLESS_TEMPLATE.format(
        outcome_path=expected_outcome_path,
    )
    assert expected_outcome_path in (output_format.text or "")
    assert "TaskCreate" in (output_format.text or "")
    assert "MCP" in (output_format.text or "")

    execution = root.find("execution")
    assert execution is not None
    all_step_texts = [each_step.text or "" for each_step in execution]
    joined_steps = " ".join(all_step_texts).lower()
    assert "do not stage, commit, or push" in joined_steps
    assert "push the commit" not in joined_steps

    constraints = root.find("constraints")
    assert constraints is not None
    all_constraint_texts = [each_constraint.text or "" for each_constraint in constraints]
    joined_constraints = " ".join(all_constraint_texts).lower()
    assert "do not stage, commit, or push" in joined_constraints


def test_main_headless_flavor_emits_outcome_path_on_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    findings_json_path = _write_findings_json(tmp_path)
    worktree_path = "/tmp/bugteam-pr-99/worktree"
    exit_code = build_fix_prompt.main([
        "--owner", "jl-cmd",
        "--repo", "claude-dev-env",
        "--pr-number", "99",
        "--loop", "2",
        "--head-ref", "feat/branch",
        "--base-ref", "main",
        "--worktree-path", worktree_path,
        "--findings-json", str(findings_json_path),
        "--flavor", FIX_PROMPT_FLAVOR_HEADLESS,
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    expected_outcome = (
        Path(worktree_path)
        / FIX_OUTCOME_XML_TEMPLATE.format(number=99, loop=2)
    ).as_posix()
    assert expected_outcome in captured.out
    assert "Do not post replies" in captured.out
    assert "Do not stage, commit, or push" in captured.out
    assert "add_reply_to_pull_request_comment" not in captured.out
