"""Contract checks for the orchestrator-as-advisor skill text."""

from pathlib import Path


_SKILL_DIR = Path(__file__).resolve().parent
_SKILL_PATH = _SKILL_DIR / "SKILL.md"
_REFRESH_PATH = _SKILL_DIR.parent / "orchestrator-refresh" / "SKILL.md"
_CONSULT_PATH = _SKILL_DIR / "reference" / "consult-the-orchestrator.md"
_BLOCK_PATH = _SKILL_DIR / "reference" / "executor-consult-block.md"


def test_orchestrator_skill_omits_bind_protocol_path() -> None:
    text = _SKILL_PATH.read_text(encoding="utf-8")
    assert "Bind the shared advisor" not in text
    for line in text.splitlines():
        if "advisor-protocol.md" in line:
            assert "Do not open" in line
    assert "reference/consult-the-orchestrator.md" in text
    assert "reference/executor-consult-block.md" in text
    assert "This session is the advisor" in text


def test_orchestrator_skill_does_not_cite_session_advisor_agent() -> None:
    text = _SKILL_PATH.read_text(encoding="utf-8")
    assert "agents/session-advisor.md" not in text
    assert "_shared/advisor/reference/advisor-block.md" not in text


def test_refresh_routes_consults_to_this_session() -> None:
    text = _REFRESH_PATH.read_text(encoding="utf-8")
    assert "This session is the advisor." in text
    assert "Hard decisions go to the shared advisor." not in text
    assert "consult-the-orchestrator.md" in text


def test_consult_contract_names_human_as_next_hop() -> None:
    text = _CONSULT_PATH.read_text(encoding="utf-8")
    assert "orchestrating session is the advisor" in text
    assert "human operating that session" in text
    assert "Do not spawn" in text
    assert "session-advisor" in text


def test_executor_consult_block_names_orchestrating_session() -> None:
    text = _BLOCK_PATH.read_text(encoding="utf-8")
    assert "<orchestrator-name>" in text
    assert "your advisor" in text
    assert "Do not use `_shared/advisor/reference/advisor-block.md`" in text
