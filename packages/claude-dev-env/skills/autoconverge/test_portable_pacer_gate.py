"""Contract checks: autoconverge selects a portable pacer when Workflow is absent."""

from __future__ import annotations

import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent
SKILL_MARKDOWN_PATH = SKILL_ROOT / "SKILL.md"
MULTI_PR_MARKDOWN_PATH = SKILL_ROOT / "reference" / "multi-pr.md"
PORTABLE_DRIVER_PATH = (
    SKILL_ROOT.parent / "_shared" / "pr-loop" / "portable-driver.md"
)

SELECT_CONVERGE_PACER_SCRIPT = "select_converge_pacer.py"
PACER_PORTABLE_TOKEN = "pacer=portable"
PACER_WORKFLOW_TOKEN = "pacer=workflow"
ABORT_ONLY_PHRASE = "autoconverge requires the Workflow tool"
PORTABLE_DRIVER_DOC = "portable-driver.md"
PORTABLE_DRIVER_LINK_PATTERN = re.compile(
    r"\((?P<relative>(?:\.\./)+_shared/pr-loop/portable-driver\.md)\)"
)


def test_skill_selects_pacer_and_forbids_abort_only_workflow() -> None:
    skill_text = SKILL_MARKDOWN_PATH.read_text(encoding="utf-8")
    assert SELECT_CONVERGE_PACER_SCRIPT in skill_text
    assert PACER_PORTABLE_TOKEN in skill_text
    assert PACER_WORKFLOW_TOKEN in skill_text
    assert PORTABLE_DRIVER_DOC in skill_text
    assert ABORT_ONLY_PHRASE not in skill_text


def test_skill_portable_driver_links_resolve_on_disk() -> None:
    skill_text = SKILL_MARKDOWN_PATH.read_text(encoding="utf-8")
    all_relative_links = PORTABLE_DRIVER_LINK_PATTERN.findall(skill_text)
    assert all_relative_links, "SKILL.md must link portable-driver.md"
    for each_relative_link in all_relative_links:
        resolved_path = (SKILL_MARKDOWN_PATH.parent / each_relative_link).resolve()
        assert resolved_path.is_file(), (
            f"portable-driver link must resolve on disk: "
            f"{each_relative_link} -> {resolved_path}"
        )
        assert resolved_path == PORTABLE_DRIVER_PATH.resolve()


def test_multi_pr_documents_portable_launch_and_teardown() -> None:
    multi_pr_text = MULTI_PR_MARKDOWN_PATH.read_text(encoding="utf-8")
    assert PACER_PORTABLE_TOKEN in multi_pr_text
    assert "Do **not** call `Workflow`" in multi_pr_text or (
        "Do not call `Workflow`" in multi_pr_text
    )
    assert "pacer=portable" in multi_pr_text
    assert PORTABLE_DRIVER_DOC in multi_pr_text
