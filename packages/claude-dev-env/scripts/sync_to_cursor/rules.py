"""Build Cursor .mdc bodies from Claude rules and docs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sync_to_cursor.config import MAX_RULE_BODY_LINES


def _parse_h2_sections(markdown: str) -> dict[str, str]:
    parts = re.split(r"^## ", markdown, flags=re.MULTILINE)
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
        "under `~/.claude/system-prompts/software-engineer.xml` when needed.)_"
    )


def _strip_code_standards_blockquote(markdown: str) -> str:
    lines = markdown.splitlines()
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
        line for line in code_standards_markdown.splitlines() if not line.strip().startswith("- TDD ")
    )
    code_rules_markdown = sources[1].read_text(encoding="utf-8")
    sections_by_heading = _parse_h2_sections(code_rules_markdown)
    if not sections_by_heading:
        pointer_fallback_note = (
            "_(Full code-quality rules: `~/.claude/system-prompts/software-engineer.xml`"
            " under `<code_quality>`.)_"
        )
        chunks = [code_standards_markdown, "", pointer_fallback_note]
        return _limit_lines("\n\n".join(chunks), MAX_RULE_BODY_LINES)
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


def _frontmatter(description: str, always_apply: bool, globs: str | None) -> str:
    escaped_description = description.replace('"', '\\"')
    lines = ["---", f'description: "{escaped_description}"']
    if globs:
        escaped_globs = globs.replace('"', '\\"')
        lines.append(f'globs: "{escaped_globs}"')
    lines.append(f"alwaysApply: {'true' if always_apply else 'false'}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _full_mdc(mapping: RuleMapping, body: str) -> str:
    generated_header = (
        "<!-- Generated by sync-to-cursor.py — do not edit directly -->\n"
        "<!-- Re-run: python ~/.claude/scripts/sync-to-cursor.py -->\n"
        "<!-- Output: .cursor/rules/*.mdc, .cursor/docs/*.md"
        " (see LLM_SETTINGS_ROOT in script docstring) -->\n"
    )
    return _frontmatter(mapping.description, mapping.always_apply, mapping.globs) + "\n" + generated_header + "\n" + body + "\n"


def _read_paths_glob(rule_file: Path) -> str | None:
    """Read `paths:` list from a Claude rule's YAML frontmatter; return as comma-separated Cursor glob string."""
    if not rule_file.is_file():
        return None
    lines = rule_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    is_in_paths = False
    all_paths: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("paths:"):
            is_in_paths = True
            continue
        if is_in_paths:
            if line.startswith(" ") or line.startswith("\t"):
                path_value = line.strip().lstrip("-").strip().strip('"').strip("'")
                if path_value:
                    all_paths.append(path_value)
            else:
                is_in_paths = False
    return ",".join(all_paths) if all_paths else None


def build_mappings(claude: Path) -> tuple[RuleMapping, ...]:
    rules_directory = claude / "rules"
    docs_directory = claude / "docs"
    test_globs = "**/*.test.*,**/*.spec.*,**/test_*,**/*_test.*"
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
            _read_paths_glob(rules_directory / "tasklings-preferences.md"),
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
            test_globs,
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
