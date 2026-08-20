"""Fixtures for the Opus 5 communication contract on installed surfaces.

Stable marker: ``opus5-communication-contract-v1``. Fixtures assert the marker
and key phrases on the package rule/prompt surfaces, not live model transcripts.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT: Path = Path(__file__).resolve().parents[1] / "packages" / "claude-dev-env"
CONTRACT_MARKER: str = "opus5-communication-contract-v1"
CONTRACT_PATH: Path = PACKAGE_ROOT / "rules" / "opus5-communication-contract.md"
ELI11_PATH: Path = PACKAGE_ROOT / "rules" / "eli11-replies.md"
PLAIN_LANGUAGE_PATH: Path = PACKAGE_ROOT / "rules" / "plain-language.md"
LONG_HORIZON_PATH: Path = PACKAGE_ROOT / "rules" / "long-horizon-autonomy.md"
CLAUDE_MD_PATH: Path = PACKAGE_ROOT / ".claude" / "CLAUDE.md"
AGENTS_MD_PATH: Path = PACKAGE_ROOT / "AGENTS.md"
SOFTWARE_ENGINEER_PATH: Path = (
    PACKAGE_ROOT / "system-prompts" / "software-engineer.xml"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_contract_file_carries_marker_and_core_phrases() -> None:
    contract_text = _read(CONTRACT_PATH)
    assert CONTRACT_MARKER in contract_text
    lowered = contract_text.lower()
    assert "first progress update is one sentence" in lowered
    assert "important discoveries or a direction change" in lowered
    assert "final starts with the outcome" in lowered
    assert "internal-system XML" in contract_text
    assert "no fitting tool exists" in contract_text


def test_short_answer_and_full_audit_examples_exist() -> None:
    contract_text = _read(CONTRACT_PATH)
    assert "### Short answer" in contract_text
    assert "### Requested full audit" in contract_text
    assert "### First progress update" in contract_text
    assert "### Outcome-first final" in contract_text


def test_eli11_and_claude_md_point_at_contract() -> None:
    assert CONTRACT_MARKER in _read(ELI11_PATH)
    assert "opus5-communication-contract" in _read(ELI11_PATH)
    assert CONTRACT_MARKER in _read(AGENTS_MD_PATH)
    assert _read(CLAUDE_MD_PATH) == "@../AGENTS.md\n"


def test_plain_language_links_contract_without_restating() -> None:
    plain_text = _read(PLAIN_LANGUAGE_PATH)
    assert "opus5-communication-contract" in plain_text


def test_long_horizon_progress_phrases_without_touching_delegation() -> None:
    long_horizon_text = _read(LONG_HORIZON_PATH)
    assert "first progress update is one sentence" in long_horizon_text
    assert "important discoveries or a direction change" in long_horizon_text
    assert "## Delegate and keep working" in long_horizon_text


def test_software_engineer_has_communication_contract_reminder() -> None:
    prompt_text = _read(SOFTWARE_ENGINEER_PATH)
    assert "communication_contract" in prompt_text
    assert CONTRACT_MARKER in prompt_text
    assert "first progress update is one sentence" in prompt_text
    assert "internal-system XML" in prompt_text
    assert "full audit" in prompt_text.lower() or "requested full audit" in prompt_text


def test_eli11_still_owns_outcome_first_shape() -> None:
    eli11_text = _read(ELI11_PATH)
    assert "Outcome first" in eli11_text
    assert "Conclusion first" in eli11_text
