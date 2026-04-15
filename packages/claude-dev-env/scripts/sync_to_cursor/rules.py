"""Build Cursor .mdc bodies from Claude rules and docs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sync_to_cursor.constants import HEADER, MAX_RULE_BODY_LINES, TEST_GLOBS


def _parse_h2_sections(md: str) -> dict[str, str]:
    parts = re.split(r"^## ", md, flags=re.MULTILINE)
    sections: dict[str, str] = {}
    for part in parts[1:]:
        title_line, _, body = part.partition("\n")
        sections[title_line.strip()] = body.strip()
    return sections


def _filter_core_principles(body: str) -> str:
    lines = []
    for line in body.splitlines():
        if "readability-review" in line or "readability standard" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _limit_lines(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return (
        "\n".join(lines[:max_lines])
        + "\n\n_(Truncated for Cursor rule length; see the synced reference in `.cursor/docs/` "
        "(`CODE_RULES.md` or `TEST_QUALITY.md` as applicable) and follow its canonical source "
        "under `~/.claude/docs` when needed.)_"
    )


def _strip_code_standards_blockquote(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith(">") and "MANDATORY REFERENCE" in lines[i]:
            while i < len(lines) and lines[i].startswith(">"):
                i += 1
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip()


def merge_code_standards(sources: tuple[Path, ...]) -> str:
    code_standards_markdown = _strip_code_standards_blockquote(
        sources[0].read_text(encoding="utf-8")
    )
    code_standards_markdown = "\n".join(
        ln for ln in code_standards_markdown.splitlines() if not ln.strip().startswith("- TDD ")
    )
    code_rules_markdown = sources[1].read_text(encoding="utf-8")
    sections_by_heading = _parse_h2_sections(code_rules_markdown)
    include_order = [
        "COMMENT PRESERVATION (ABSOLUTE RULE)",
        "CORE PRINCIPLES",
        "⚡ HOOK-ENFORCED RULES",
        "4. CONFIG LOCATIONS",
        "5. NO ABBREVIATIONS",
        "6. COMPLETE TYPE HINTS",
        "9. SELF-CONTAINED COMPONENTS",
    ]
    chunks = [
        code_standards_markdown,
        "",
        "## Reference (full text: `.cursor/docs/CODE_RULES.md`)",
    ]
    for title in include_order:
        body = sections_by_heading.get(title, "")
        if title == "CORE PRINCIPLES":
            body = _filter_core_principles(body)
        if body:
            chunks.append(f"## {title}\n\n{body}")
    merged = "\n\n".join(chunks)
    return _limit_lines(merged, MAX_RULE_BODY_LINES)


def merge_test_quality(sources: tuple[Path, ...]) -> str:
    testing = sources[0].read_text(encoding="utf-8").strip()
    test_quality_markdown = sources[1].read_text(encoding="utf-8")
    sections_by_heading = _parse_h2_sections(test_quality_markdown)
    include_order = [
        "Delete Useless Tests",
        "Test Dependencies MUST FAIL",
        "Core Testing Principles",
        "React Testing Patterns",
        "Test File Organization",
    ]
    chunks = [testing, "", "## Reference (full text: `.cursor/docs/TEST_QUALITY.md`)"]
    for title in include_order:
        body = sections_by_heading.get(title, "")
        if body:
            chunks.append(f"## {title}\n\n{body}")
    merged = "\n\n".join(chunks)
    return _limit_lines(merged, MAX_RULE_BODY_LINES)


def strip_anthropic_refs(text: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("Source:") and (
            "anthropic" in s.lower()
            or "claude.com" in s.lower()
            or "docs.anthropic" in s.lower()
        ):
            continue
        if "docs.anthropic.com" in line:
            continue
        out_lines.append(line)
    text = "\n".join(out_lines)
    text = re.sub(
        r"<do_not_act_before_instructions>\s*",
        "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"\s*</do_not_act_before_instructions>", "", text)
    return text.strip()


def verbatim(text: str) -> str:
    return text.strip()


def near_verbatim(text: str) -> str:
    return strip_anthropic_refs(text)


def strip_leading_yaml_frontmatter(text: str) -> str:
    """Remove leading `---` ... `---` block (e.g. Claude `paths:`) so Cursor `.mdc` uses its own frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :]).lstrip("\n")
    return text


TransformName = Literal["verbatim", "near_verbatim", "merge_code_standards", "merge_test_quality"]


def apply_transform(
    name: TransformName,
    sources: tuple[Path, ...],
    *,
    strip_leading_frontmatter: bool = False,
) -> str:
    if name == "merge_code_standards":
        return merge_code_standards(sources)
    if name == "merge_test_quality":
        return merge_test_quality(sources)
    raw = "\n\n".join(p.read_text(encoding="utf-8") for p in sources)
    if strip_leading_frontmatter:
        raw = strip_leading_yaml_frontmatter(raw)
    if name == "verbatim":
        return verbatim(raw)
    if name == "near_verbatim":
        return near_verbatim(raw)
    raise AssertionError(name)


@dataclass(frozen=True)
class RuleMapping:
    key: str
    sources: tuple[Path, ...]
    output_name: str
    always_apply: bool
    globs: str | None
    description: str
    transform: TransformName
    strip_leading_frontmatter: bool = False


def _frontmatter(desc: str, always_apply: bool, globs: str | None) -> str:
    lines = ["---", f"description: {desc}"]
    if globs:
        lines.append(f"globs: {globs}")
    lines.append(f"alwaysApply: {'true' if always_apply else 'false'}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _full_mdc(mapping: RuleMapping, body: str) -> str:
    return _frontmatter(mapping.description, mapping.always_apply, mapping.globs) + "\n" + HEADER + "\n" + body + "\n"


def build_mappings(claude: Path) -> tuple[RuleMapping, ...]:
    rules_directory = claude / "rules"
    docs_directory = claude / "docs"
    return (
        RuleMapping(
            "code-standards",
            (rules_directory / "code-standards.md", docs_directory / "CODE_RULES.md"),
            "code-standards.mdc",
            True,
            None,
            "Core code standards: naming, types, config, hook-enforced rules",
            "merge_code_standards",
        ),
        RuleMapping(
            "tasklings-preferences",
            (rules_directory / "tasklings-preferences.md",),
            "tasklings-preferences.mdc",
            False,
            r"Y:/Craft a Tale/Behavioral App/Project/**",
            "Tasklings: Prefer / Do / Always engineering preferences (scoped path)",
            "verbatim",
            True,
        ),
        RuleMapping(
            "right-sized-engineering",
            (rules_directory / "right-sized-engineering.md",),
            "right-sized-engineering.mdc",
            True,
            None,
            "Right-sized engineering and complexity budget",
            "verbatim",
        ),
        RuleMapping(
            "bdd",
            (rules_directory / "bdd.md",),
            "bdd.mdc",
            True,
            None,
            "BDD: discovery-driven protocol (outside-in; Illustrate→Formulate→Automate)",
            "verbatim",
        ),
        RuleMapping(
            "test-quality",
            (rules_directory / "testing.md", docs_directory / "TEST_QUALITY.md"),
            "test-quality.mdc",
            False,
            TEST_GLOBS,
            "Testing quality for test files",
            "merge_test_quality",
        ),
        RuleMapping(
            "research-mode",
            (rules_directory / "research-mode.md",),
            "research-mode.mdc",
            True,
            None,
            "Research mode: citations and I don't know",
            "near_verbatim",
        ),
        RuleMapping(
            "conservative-action",
            (rules_directory / "conservative-action.md",),
            "conservative-action.mdc",
            True,
            None,
            "Prefer research over action when intent is unclear",
            "near_verbatim",
        ),
        RuleMapping(
            "explore-thoroughly",
            (rules_directory / "explore-thoroughly.md",),
            "explore-thoroughly.mdc",
            True,
            None,
            "Explore codebase before committing to an approach",
            "near_verbatim",
        ),
    )
