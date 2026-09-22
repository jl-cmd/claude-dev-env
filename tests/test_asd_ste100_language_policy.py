"""Production-surface tests for the ASD-STE100 language policy."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "packages" / "claude-dev-env"
CANONICAL_RULE_PATH = PACKAGE_ROOT / "rules" / "asd-ste100-language.md"
ACTIVE_RUNTIME_PROJECTION_PATHS = (
    ".cursor/BUGBOT.md",
    "docs/references/tabbed-decision-artifact-template.md",
    "docs/references/tabbed-decision-artifact-template.html",
    "packages/claude-dev-env/system-prompts/software-engineer.xml",
    "packages/claude-dev-env/.agents/skills/eli5/SKILL.md",
    "packages/claude-dev-env/commands/sr-loop.md",
    "packages/claude-dev-env/_shared/advisor/reference/third-party-bind.md",
    "packages/claude-dev-env/hooks/session/working_style_prompt.py",
    "packages/claude-dev-env/hooks/session/test_working_style_prompt.py",
    "packages/claude-dev-env/hooks/hooks_constants/working_style_prompt_constants.py",
    "packages/claude-dev-env/hooks/blocking/state_description_blocker.py",
    "packages/claude-dev-env/hooks/blocking/test_state_description_blocker.py",
    "packages/claude-dev-env/docs/references/prose-style-enforcement.md",
)
RETIRED_LANGUAGE_REFERENCES = (
    "plain-language.md",
    "eli11-replies.md",
    "opus5-communication-contract.md",
    "doc-prose-cuts.md",
    "opus5-communication-contract-v1",
)


def _read(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def test_canonical_rule_has_issue_9_sources_and_adaptation_boundary() -> None:
    canonical_text = _read(CANONICAL_RULE_PATH)
    lowered_text = canonical_text.lower()

    assert "asd-ste100 simplified technical english, issue 9 (2025-01-15)" in lowered_text
    assert "asd-ste100 issue 9 conversational adaptation" in lowered_text
    assert "https://www.asd-ste100.org/assets/files/asd-ste100_issue9.pdf" in lowered_text
    assert "https://www.asd-ste100.org/ste_faq.html" in lowered_text
    assert "https://www.asd-ste100.org/about_ste.html" in lowered_text
    assert not canonical_text.startswith("---")


def test_canonical_rule_contains_compact_policy_clauses() -> None:
    canonical_text = _read(CANONICAL_RULE_PATH).lower()
    required_clauses = (
        "short, complete sentences",
        "one topic in each explanatory sentence",
        "active voice",
        "one action in each sentence",
        "familiar, precise words",
        "stable term",
        "full words and explicit references",
        "inclusive, neutral language",
        "periods, commas, colons, and bullets",
        "exact quoted labels",
        "`warning`",
        "`caution`",
        "20 words or fewer",
        "25 words or fewer",
        "responsible human verifies",
    )

    for each_clause in required_clauses:
        assert each_clause in canonical_text


def test_active_runtime_projections_use_the_canonical_language_rule() -> None:
    for each_relative_path in ACTIVE_RUNTIME_PROJECTION_PATHS:
        projection_text = _read(REPOSITORY_ROOT / each_relative_path)
        lowered_text = projection_text.lower()
        assert "asd-ste100-language" in lowered_text, each_relative_path
        for each_retired_reference in RETIRED_LANGUAGE_REFERENCES:
            assert each_retired_reference not in lowered_text, (
                f"{each_relative_path} retains {each_retired_reference}"
            )


def test_archived_session_log_preserves_its_language_policy() -> None:
    archived_path = REPOSITORY_ROOT / "skill-archive" / "session-log" / "SKILL.md"
    archived_text = _read(archived_path).lower()
    assert "asd-ste100-language" in archived_text
    assert not (PACKAGE_ROOT / ".agents" / "skills" / "session-log").exists()
    for each_retired_reference in RETIRED_LANGUAGE_REFERENCES:
        assert each_retired_reference not in archived_text
