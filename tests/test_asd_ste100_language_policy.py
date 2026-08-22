"""Production-surface tests for the ASD-STE100 language policy."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "packages" / "claude-dev-env"
CANONICAL_RULE_PATH = PACKAGE_ROOT / "rules" / "asd-ste100-language.md"
PACKAGE_HUB_PATH = PACKAGE_ROOT / "AGENTS.md"
ARCHIVE_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "records"
    / "asd-ste100-language-policy"
    / "superseded-language-specifiers.md"
)
ACTIVE_RUNTIME_PROJECTION_PATHS = (
    "AGENTS.md",
    ".cursor/BUGBOT.md",
    "docs/references/tabbed-decision-artifact-template.md",
    "docs/references/tabbed-decision-artifact-template.html",
    "packages/claude-dev-env/system-prompts/software-engineer.xml",
    "packages/claude-dev-env/system-prompts/AGENTS.md",
    "packages/claude-dev-env/.agents/skills/AGENTS.md",
    "packages/claude-dev-env/.agents/agents/AGENTS.md",
    "packages/claude-dev-env/.agents/skills/session-log/SKILL.md",
    "packages/claude-dev-env/.agents/skills/eli5/SKILL.md",
    "packages/claude-dev-env/commands/AGENTS.md",
    "packages/claude-dev-env/commands/sr-loop.md",
    "packages/claude-dev-env/_shared/AGENTS.md",
    "packages/claude-dev-env/_shared/advisor/reference/third-party-bind.md",
    "packages/claude-dev-env/_shared/pr-loop/audit-reply-template.md",
    "packages/claude-dev-env/_shared/pr-loop/fix-protocol.md",
    "packages/claude-dev-env/hooks/session/AGENTS.md",
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


def test_archive_stays_outside_the_package_rules_directory() -> None:
    archive_text = _read(ARCHIVE_PATH)
    rules_directory = PACKAGE_ROOT / "rules"
    retired_rule_names = (
        "plain-language.md",
        "eli11-replies.md",
        "opus5-communication-contract.md",
        "doc-prose-cuts.md",
    )

    assert ARCHIVE_PATH.is_file()
    assert rules_directory.joinpath("asd-ste100-language.md").is_file()
    for each_retired_rule_name in retired_rule_names:
        assert not rules_directory.joinpath(each_retired_rule_name).exists()
        assert f"packages/claude-dev-env/rules/{each_retired_rule_name}" in archive_text


def test_active_runtime_projections_use_the_canonical_language_rule() -> None:
    for each_relative_path in ACTIVE_RUNTIME_PROJECTION_PATHS:
        projection_text = _read(REPOSITORY_ROOT / each_relative_path)
        lowered_text = projection_text.lower()
        assert "asd-ste100-language" in lowered_text, each_relative_path
        for each_retired_reference in RETIRED_LANGUAGE_REFERENCES:
            assert each_retired_reference not in lowered_text, (
                f"{each_relative_path} retains {each_retired_reference}"
            )


def test_package_hub_preserves_operational_contract() -> None:
    package_text = _read(PACKAGE_HUB_PATH)
    required_operational_sections = (
        "Ask when ambiguity materially changes scope or implementation.",
        "Tests must exercise real behavior, real data, and production paths.",
        "Coders consult a warm session-advisor when blocked (Sol xHigh).",
        "Delegate fact extraction when multiple files or search patterns are required.",
        "Read or search directly only in files you will modify via es.exe.",
        "Track every task using `update_plan`.",
        "Delegate all task work to Tier 3 agents.",
        "Run independent assignments in parallel. Keep overlapping work sequential.",
        "Tier 3 agent: A strong execution specialist",
        "Only correct an earlier statement when the ecode, conclusions, or decisions.",
        "When you use a tool, you may say a brief sentence first.",
        "When reviewing code, report everything you find.",
    )

    for each_operational_section in required_operational_sections:
        assert each_operational_section in package_text
    assert "ELI5 owns beginner framing and beginner-friendly presentation" in package_text
    assert "large visuals, minimal text" in package_text
    assert "one stable self-contained HTML artifact" in package_text
    assert "update-in-place continuity" in package_text
    assert "rules/asd-ste100-language.md` owns sentence-level" in package_text
    assert "~/.claude/agents/session-advisor.md" in package_text
    assert "~/.claude/skills/everything-search/SKILL.md" in package_text
    assert "~/.claude/skills/small-cl/SKILL.md" in package_text
    assert "Use the named review workflow for code-review response reporting." in package_text


def test_package_hub_archive_carries_replaced_language_ranges() -> None:
    archive_text = _read(ARCHIVE_PATH)

    assert "Package hub language sections captured" in archive_text
    for each_range in ("1-5", "9-11", "40-101", "121-127", "133-135"):
        assert f"Origin source lines {each_range}" in archive_text
    assert "Every rule in this file governs all text everywhere" in archive_text
    assert "opus5-communication-contract-v1" in archive_text
