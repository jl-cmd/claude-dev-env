"""Markdown assertion tests for pr-converge orchestrator team lifecycle.

Locks in the contract that pr-converge multi-PR orchestration must:
  - own a single long-lived team for the whole sweep
  - pass that team to every bugteam invocation via attach mode
  - tear down only when every PR reaches `converged` or `blocked`
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType


def _skill_text() -> str:
    here = pathlib.Path(__file__).parent
    return (here / "SKILL.md").read_text(encoding="utf-8")


def test_reflow_module_restores_sys_path_after_import() -> None:
    path_snapshot = list(sys.path)
    _reflow_module()
    assert sys.path == path_snapshot


def _reflow_module() -> ModuleType:
    here = pathlib.Path(__file__).parent
    script_path = here / "scripts" / "reflow_skill_md.py"
    script_parent_entry = str(script_path.parent)
    prior_sys_path = list(sys.path)
    sys.path.insert(0, script_parent_entry)
    try:
        spec = importlib.util.spec_from_file_location("reflow_skill_md", script_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = prior_sys_path


def test_skill_documents_orchestrator_owned_team_in_multi_pr_mode() -> None:
    skill_text = _skill_text()
    assert "team_name" in skill_text
    assert "TeamCreate" in skill_text
    assert "orchestrator" in skill_text.lower()


def test_skill_passes_attach_mode_to_bugteam_invocations() -> None:
    skill_text = _skill_text()
    assert "BUGTEAM_TEAM_LIFECYCLE" in skill_text
    assert "attach" in skill_text
    assert "BUGTEAM_TEAM_NAME" in skill_text


def test_skill_tears_down_team_only_on_full_convergence() -> None:
    skill_text = _skill_text()
    assert "TeamDelete" in skill_text
    convergence_phrases = [
        "every PR",
        "all PRs",
        "fully converged",
        "every prs[",
    ]
    assert any(phrase in skill_text for phrase in convergence_phrases)


def test_state_schema_includes_team_name_field() -> None:
    skill_text = _skill_text()
    assert '"team_name"' in skill_text or "team_name:" in skill_text


def test_skill_md_physical_lines_fit_eighty_column_limit() -> None:
    skill_text = _skill_text()
    for each_line_number, each_physical_line in enumerate(skill_text.splitlines(), 1):
        assert len(each_physical_line) <= 80, (
            "SKILL.md line %s exceeds 80 columns (%s chars)"
            % (each_line_number, len(each_physical_line))
        )


def test_skill_front_matter_keeps_state_json_code_span_closed() -> None:
    skill_text = _skill_text()
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json>`" not in skill_text
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json` per" in skill_text


def test_skill_does_not_promote_inline_pr_numbers_to_headings() -> None:
    skill_text = _skill_text()
    top_level_headings = [
        each_line for each_line in skill_text.splitlines() if each_line.startswith("# ")
    ]
    assert top_level_headings == ["# PR Converge"]


def test_reflow_yaml_description_preserves_state_json_code_span() -> None:
    reflow_module = _reflow_module()
    description_lines = [
        "  Multi-PR runs persist traffic in",
        "  `<TMPDIR>/pr-converge-<session_id>/state.json` per §Multi-PR",
        "  orchestration model.",
        "---",
    ]

    reflowed_lines, next_index = reflow_module.reflow_yaml_description_block(
        description_lines,
        0,
    )

    reflowed_text = " ".join(each_line.strip() for each_line in reflowed_lines)
    assert next_index == 4
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json>`" not in reflowed_text
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json` per" in reflowed_text


def test_reflow_merges_inline_pr_number_continuations() -> None:
    reflow_module = _reflow_module()

    merged_lines = reflow_module.merge_soft_breaks(
        [
            "with title `chore: address Copilot findings from PR",
            "#<NUMBER>`; reports both PR URLs",
        ]
    )

    assert merged_lines == [
        "with title `chore: address Copilot findings from PR #<NUMBER>`; "
        "reports both PR URLs"
    ]


def test_skill_keeps_markdown_reference_definitions_separate() -> None:
    skill_text = _skill_text()
    assert "[path-b]: ../bugteam/reference/workflow-path-b-task-harness.md\n" in skill_text
    assert (
        "[path-a]: ../bugteam/reference/workflow-path-a-orchestrated-teams.md\n"
        in skill_text
    )


def test_reflow_keeps_reference_definitions_as_separate_lines() -> None:
    reflow_module = _reflow_module()

    merged_lines = reflow_module.merge_soft_breaks(
        [
            "[path-b]: ../bugteam/reference/workflow-path-b-task-harness.md",
            "[path-a]: ../bugteam/reference/workflow-path-a-orchestrated-teams.md",
        ]
    )

    assert merged_lines == [
        "[path-b]: ../bugteam/reference/workflow-path-b-task-harness.md",
        "[path-a]: ../bugteam/reference/workflow-path-a-orchestrated-teams.md",
    ]
