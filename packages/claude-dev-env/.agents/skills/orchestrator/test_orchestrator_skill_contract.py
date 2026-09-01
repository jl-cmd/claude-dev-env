"""Contract checks for the orchestrator-as-advisor skill text."""

from pathlib import Path


_SKILL_DIR = Path(__file__).resolve().parent
_REFRESH_PATH = _SKILL_DIR.parent / "orchestrator-refresh" / "SKILL.md"
_ORCHESTRATOR_PATHS = (
    _SKILL_DIR / "SKILL.md",
    _SKILL_DIR / "AGENTS.md",
    _SKILL_DIR / "reference" / "consult-the-orchestrator.md",
    _SKILL_DIR / "reference" / "executor-consult-block.md",
    _SKILL_DIR / "reference" / "host-detect.md",
    _SKILL_DIR / "reference" / "AGENTS.md",
    _REFRESH_PATH,
)
_FOREIGN_MARKERS = (
    "advisor-protocol",
    "session-advisor",
    "advisor-block.md",
    "consult-format.md",
    "advisor-tool.md",
    "_shared/advisor",
)


def test_orchestrator_docs_omit_foreign_advisor_paths() -> None:
    for path in _ORCHESTRATOR_PATHS:
        text = path.read_text(encoding="utf-8")
        for marker in _FOREIGN_MARKERS:
            assert marker not in text, f"{path.name} names {marker}"


def test_orchestrator_skill_points_at_local_consult_files() -> None:
    text = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "Bind the shared advisor" not in text
    assert "reference/consult-the-orchestrator.md" in text
    assert "reference/executor-consult-block.md" in text
    assert "This session is the advisor" in text


def test_refresh_routes_consults_to_this_session() -> None:
    text = _REFRESH_PATH.read_text(encoding="utf-8")
    assert "This session is the advisor." in text
    assert "Hard decisions go to the shared advisor." not in text
    assert "consult-the-orchestrator.md" in text


def test_consult_contract_names_human_as_next_hop() -> None:
    text = (_SKILL_DIR / "reference" / "consult-the-orchestrator.md").read_text(
        encoding="utf-8"
    )
    assert "orchestrating session is the advisor" in text
    assert "human operating that session" in text


def test_executor_consult_block_names_orchestrating_session() -> None:
    text = (_SKILL_DIR / "reference" / "executor-consult-block.md").read_text(
        encoding="utf-8"
    )
    assert "<orchestrator-name>" in text
    assert "your advisor" in text
