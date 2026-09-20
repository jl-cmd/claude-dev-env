"""Contract tests for the canonical ASD-STE100 language policy."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "packages" / "claude-dev-env"
CANONICAL_RULE_PATH = PACKAGE_ROOT / "rules" / "asd-ste100-language.md"


def _read(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def test_canonical_rule_owns_general_language_contract() -> None:
    canonical_text = _read(CANONICAL_RULE_PATH)
    lowered_text = canonical_text.lower()

    assert "asd-ste100 simplified technical english, issue 9 (2025-01-15)" in lowered_text
    assert "asd-ste100 issue 9 conversational adaptation" in lowered_text
    assert "https://www.asd-ste100.org/assets/files/asd-ste100_issue9.pdf" in lowered_text
    assert "https://www.asd-ste100.org/ste_faq.html" in lowered_text
    assert "short, complete sentences" in lowered_text
    assert "one topic in each explanatory sentence" in lowered_text
    assert "active voice" in lowered_text
    assert "one action in each sentence" in lowered_text
    assert "familiar, precise words" in lowered_text
    assert "stable term" in lowered_text
    assert "full words and explicit references" in lowered_text
    assert "inclusive, neutral language" in lowered_text
    assert "periods, commas, colons, and bullets" in lowered_text
    assert "exact quoted labels" in lowered_text
    assert "warning" in lowered_text
    assert "caution" in lowered_text
    assert "20 words or fewer" in lowered_text
    assert "25 words or fewer" in lowered_text
    assert "responsible human verifies" in lowered_text
    assert not canonical_text.startswith("---")
