"""Contract checks: pr-converge selects a portable pacer when ScheduleWakeup is absent."""

from __future__ import annotations

import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent
SKILL_MARKDOWN_PATH = SKILL_ROOT / "SKILL.md"
PER_TICK_MARKDOWN_PATH = SKILL_ROOT / "reference" / "per-tick.md"
PORTABLE_DRIVER_PATH = (
    SKILL_ROOT.parent / "_shared" / "pr-loop" / "portable-driver.md"
)

SELECT_CONVERGE_PACER_SCRIPT = "select_converge_pacer.py"
PACER_PORTABLE_TOKEN = "pacer=portable"
PACER_SCHEDULE_WAKEUP_TOKEN = "pacer=schedule_wakeup"
ABORT_ONLY_PHRASE = "pr-converge requires ScheduleWakeup; aborting"
PORTABLE_DRIVER_DOC = "portable-driver.md"
PORTABLE_DRIVER_LINK_PATTERN = re.compile(
    r"\((?P<relative>(?:\.\./)+_shared/pr-loop/portable-driver\.md)\)"
)


def test_skill_selects_pacer_and_forbids_abort_only_schedule_wakeup() -> None:
    skill_text = SKILL_MARKDOWN_PATH.read_text(encoding="utf-8")
    assert SELECT_CONVERGE_PACER_SCRIPT in skill_text
    assert PACER_PORTABLE_TOKEN in skill_text
    assert PACER_SCHEDULE_WAKEUP_TOKEN in skill_text
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


def test_per_tick_documents_both_pacers() -> None:
    per_tick_text = PER_TICK_MARKDOWN_PATH.read_text(encoding="utf-8")
    assert "portable" in per_tick_text
    assert "schedule_wakeup" in per_tick_text or "ScheduleWakeup" in per_tick_text
    assert PORTABLE_DRIVER_DOC in per_tick_text
    assert "pacer=portable" in per_tick_text
    assert "Do **not** call `ScheduleWakeup`" in per_tick_text or (
        "Do not call `ScheduleWakeup`" in per_tick_text
    )


def test_portable_driver_protocol_exists() -> None:
    assert PORTABLE_DRIVER_PATH.is_file()
    portable_text = PORTABLE_DRIVER_PATH.read_text(encoding="utf-8")
    assert "check_convergence.py" in portable_text
    assert "invoke_code_review.py" in portable_text
    assert "resolve_worker_spawn.py" in portable_text
    assert "Never** abort solely because" in portable_text or (
        "Never abort solely because" in portable_text
    )
