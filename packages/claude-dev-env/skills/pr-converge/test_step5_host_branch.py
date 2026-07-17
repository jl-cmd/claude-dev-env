"""Contract checks for Step 5 host-aware CODE_REVIEW wiring.

Issue #103: Step 5 names ``invoke_code_review.py``, the mode decision inputs
(host profile, session model), stdin/cwd rules, and the clean/dirty branches
without changing ``code_review_clean_at`` semantics.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent
PROGRESS_CHECKLIST_MARKDOWN_PATH = SKILL_ROOT / "reference" / "progress-checklist.md"
PER_TICK_MARKDOWN_PATH = SKILL_ROOT / "reference" / "per-tick.md"

HELPER_SCRIPT_NAME = "invoke_code_review.py"
SESSION_MODEL_FLAG = "--session-model"
HOST_PROFILE_PHRASE = "host profile"
SESSION_MODEL_PHRASE = "session model"
IN_SESSION_MODE = "in_session"
CHAIN_MODE = "chain"
DIRTY_TREE_KEY = "dirty_tree"
RETURNCODE_KEY = "returncode"
SERVED_COMMAND_KEY = "served_command"
SUCCESSFUL_SERVE_PHRASE = "successful serve"
FAILED_REVIEW_PHRASE = "Failed review"
CODE_REVIEW_CLEAN_AT = "code_review_clean_at"
CLEAN_STAMP_HELPER = "is_code_review_clean_stamp_allowed"
NEVER_COMMITS_PHRASE = "never commits"
NEVER_PUSHES_PHRASE = "never pushes"
EMPTY_STDIN_PHRASE = "empty"
CWD_FLAG = "--cwd"
OPUS_MODEL = "opus"
HIGH_EFFORT_SLASH = "/code-review xhigh --fix"


def _read_markdown(markdown_path: Path) -> str:
    return markdown_path.read_text(encoding="utf-8")


def _code_review_section(per_tick_text: str) -> str:
    section_start = per_tick_text.index("### `phase == CODE_REVIEW`")
    section_end = per_tick_text.index("### `phase == BUGTEAM`", section_start)
    return per_tick_text[section_start:section_end]


def _step_five_checklist(progress_checklist_text: str) -> str:
    step_start = progress_checklist_text.index("**Step 5: CODE-REVIEW")
    step_end = progress_checklist_text.index("**Step 6: BUGTEAM", step_start)
    return progress_checklist_text[step_start:step_end]


def test_per_tick_code_review_names_helper_and_mode_inputs() -> None:
    code_review_section = _code_review_section(_read_markdown(PER_TICK_MARKDOWN_PATH))
    assert HELPER_SCRIPT_NAME in code_review_section
    assert HOST_PROFILE_PHRASE in code_review_section
    assert SESSION_MODEL_PHRASE in code_review_section
    assert SESSION_MODEL_FLAG in code_review_section
    assert CWD_FLAG in code_review_section
    assert IN_SESSION_MODE in code_review_section
    assert CHAIN_MODE in code_review_section
    assert DIRTY_TREE_KEY in code_review_section
    assert RETURNCODE_KEY in code_review_section
    assert SERVED_COMMAND_KEY in code_review_section
    assert SUCCESSFUL_SERVE_PHRASE in code_review_section
    assert FAILED_REVIEW_PHRASE in code_review_section
    assert CLEAN_STAMP_HELPER in code_review_section
    assert HIGH_EFFORT_SLASH in code_review_section
    assert OPUS_MODEL in code_review_section
    assert NEVER_COMMITS_PHRASE in code_review_section
    assert NEVER_PUSHES_PHRASE in code_review_section
    assert EMPTY_STDIN_PHRASE in code_review_section
    assert CODE_REVIEW_CLEAN_AT in code_review_section


def test_skill_step_five_checklist_names_helper_and_mode_inputs() -> None:
    step_five_checklist = _step_five_checklist(
        _read_markdown(PROGRESS_CHECKLIST_MARKDOWN_PATH)
    )
    assert HELPER_SCRIPT_NAME in step_five_checklist
    assert HOST_PROFILE_PHRASE in step_five_checklist
    assert SESSION_MODEL_PHRASE in step_five_checklist
    assert SESSION_MODEL_FLAG in step_five_checklist
    assert CWD_FLAG in step_five_checklist
    assert IN_SESSION_MODE in step_five_checklist
    assert CHAIN_MODE in step_five_checklist
    assert DIRTY_TREE_KEY in step_five_checklist
    assert RETURNCODE_KEY in step_five_checklist
    assert SERVED_COMMAND_KEY in step_five_checklist
    assert SUCCESSFUL_SERVE_PHRASE in step_five_checklist
    assert HIGH_EFFORT_SLASH in step_five_checklist
    assert OPUS_MODEL in step_five_checklist
    assert NEVER_COMMITS_PHRASE in step_five_checklist
    assert NEVER_PUSHES_PHRASE in step_five_checklist
    assert CODE_REVIEW_CLEAN_AT in step_five_checklist


def test_per_tick_clean_stamp_requires_successful_serve() -> None:
    code_review_section = _code_review_section(_read_markdown(PER_TICK_MARKDOWN_PATH))
    assert FAILED_REVIEW_PHRASE in code_review_section
    assert "returncode != 0" in code_review_section
    assert "null" in code_review_section
    assert SERVED_COMMAND_KEY in code_review_section
    assert "do not set" in code_review_section.lower() or "Do not set" in code_review_section
    assert CODE_REVIEW_CLEAN_AT in code_review_section
    assert SUCCESSFUL_SERVE_PHRASE in code_review_section
    assert DIRTY_TREE_KEY in code_review_section
