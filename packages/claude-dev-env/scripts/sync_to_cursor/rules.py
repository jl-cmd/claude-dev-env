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
    for each_part in parts[1:]:
        title_line, _, body = each_part.partition("\n")
        sections[title_line.strip()] = body.strip()
    return sections


def _filter_core_principles(body: str) -> str:
    lines = []
    for each_line in body.splitlines():
        if "readability standard" in each_line:
            continue
        lines.append(each_line)
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


_merged_mapping_key_order = (
    "code-standards",
    "tasklings-preferences",
    "right-sized-engineering",
    "bdd",
    "test-quality",
    "research-mode",
    "conservative-action",
    "explore-thoroughly",
)

_code_standards_section_order = (
    "COMMENT PRESERVATION (ABSOLUTE RULE)",
    "CORE PRINCIPLES",
    "⚡ HOOK-ENFORCED RULES",
    "3. REUSE CONSTANTS / 4. CONFIG LOCATIONS",
    "5. NO ABBREVIATIONS",
    "6. COMPLETE TYPE HINTS",
    "9. SELF-CONTAINED COMPONENTS",
)

_test_quality_section_order = (
    "Delete Useless Tests",
    "Test Dependencies MUST FAIL",
    "Core Testing Principles",
    "React Testing Patterns",
    "Test File Organization",
)


def merge_code_standards(all_sources: tuple[Path, ...]) -> str:
    """Merge the code-standards rule and CODE_RULES doc into one Cursor rule body.

    Args:
        all_sources: The code-standards rule path then the CODE_RULES doc path.

    Returns:
        The merged Cursor rule body, truncated to the maximum rule body length.
    """
    code_standards_markdown = _strip_code_standards_blockquote(
        all_sources[0].read_text(encoding="utf-8")
    )
    code_standards_markdown = "\n".join(
        each_line
        for each_line in code_standards_markdown.splitlines()
        if not each_line.strip().startswith("- TDD ")
    )
    code_rules_markdown = all_sources[1].read_text(encoding="utf-8")
    sections_by_heading = _parse_h2_sections(code_rules_markdown)
    if not sections_by_heading:
        pointer_fallback_note = (
            "_(Full code-quality rules: `~/.claude/system-prompts/software-engineer.xml`"
            " under `<code_quality>`.)_"
        )
        chunks = [code_standards_markdown, "", pointer_fallback_note]
        return _limit_lines("\n\n".join(chunks), MAX_RULE_BODY_LINES)
    chunks = [
        code_standards_markdown,
        "",
        "## Reference (full text: `.cursor/docs/CODE_RULES.md`)",
    ]
    for each_title in _code_standards_section_order:
        assert each_title in sections_by_heading, (
            f"merge_code_standards: expected section absent from CODE_RULES.md: {each_title}"
        )
        body = sections_by_heading[each_title]
        if each_title == "CORE PRINCIPLES":
            body = _filter_core_principles(body)
        if body:
            chunks.append(f"## {each_title}\n\n{body}")
    merged = "\n\n".join(chunks)
    return _limit_lines(merged, MAX_RULE_BODY_LINES)


def merge_test_quality(all_sources: tuple[Path, ...]) -> str:
    """Merge the testing rule and TEST_QUALITY doc into one Cursor rule body.

    Args:
        all_sources: The testing rule path then the TEST_QUALITY doc path.

    Returns:
        The merged Cursor rule body, truncated to the maximum rule body length.
    """
    testing = strip_leading_yaml_frontmatter(
        all_sources[0].read_text(encoding="utf-8")
    ).strip()
    test_quality_markdown = all_sources[1].read_text(encoding="utf-8")
    sections_by_heading = _parse_h2_sections(test_quality_markdown)
    chunks = [testing, "", "## Reference (full text: `.cursor/docs/TEST_QUALITY.md`)"]
    for each_title in _test_quality_section_order:
        assert each_title in sections_by_heading, (
            f"merge_test_quality: expected section absent from TEST_QUALITY.md: {each_title}"
        )
        body = sections_by_heading[each_title]
        if body:
            chunks.append(f"## {each_title}\n\n{body}")
    merged = "\n\n".join(chunks)
    return _limit_lines(merged, MAX_RULE_BODY_LINES)


def strip_anthropic_refs(text: str) -> str:
    """Remove Anthropic source citations and the do-not-act wrapper from rule text.

    Args:
        text: The rule body to clean.

    Returns:
        The rule body without Anthropic citation lines or the wrapper tags.
    """
    out_lines: list[str] = []
    for each_line in text.splitlines():
        stripped_line = each_line.strip()
        if stripped_line.startswith("Source:") and (
            "anthropic" in stripped_line.lower()
            or "claude.com" in stripped_line.lower()
            or "docs.anthropic" in stripped_line.lower()
        ):
            continue
        if "docs.anthropic.com" in each_line:
            continue
        out_lines.append(each_line)
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
    """Remove a leading `---` ... `---` block so Cursor `.mdc` keeps its own frontmatter.

    Args:
        text: The rule body that may open with a Claude YAML frontmatter block.

    Returns:
        The rule body with any leading frontmatter block removed.
    """
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
    all_sources: tuple[Path, ...],
    *,
    strip_leading_frontmatter: bool = False,
) -> str:
    """Run the named transform over the source files and return the rule body.

    Args:
        name: The transform identifier selecting how the sources combine.
        all_sources: The source files the transform reads.
        strip_leading_frontmatter: When True, drop a leading YAML frontmatter
            block from the raw concatenation before a verbatim transform.

    Returns:
        The transformed Cursor rule body.

    Raises:
        AssertionError: When *name* is not a recognized transform identifier.
    """
    if name == "merge_code_standards":
        return merge_code_standards(all_sources)
    if name == "merge_test_quality":
        return merge_test_quality(all_sources)
    raw = "\n\n".join(each_source.read_text(encoding="utf-8") for each_source in all_sources)
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
        "<!-- Generated by sync_to_cursor.py — do not edit directly -->\n"
        "<!-- Re-run: python ~/.claude/scripts/sync_to_cursor.py -->\n"
        "<!-- Output: .cursor/rules/*.mdc, .cursor/docs/*.md"
        " (see LLM_SETTINGS_ROOT in script docstring) -->\n"
    )
    return _frontmatter(mapping.description, mapping.always_apply, mapping.globs) + "\n" + generated_header + "\n" + body + "\n"


def _read_paths_glob(rule_file: Path) -> str | None:
    """Read the `paths:` list from a Claude rule's YAML frontmatter as a Cursor glob.

    Args:
        rule_file: The Claude rule file whose frontmatter may declare `paths:`.

    Returns:
        The comma-separated glob string, or None when the rule declares no paths.
    """
    if not rule_file.is_file():
        return None
    lines = rule_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    is_in_paths = False
    all_paths: list[str] = []
    for each_line in lines[1:]:
        if each_line.strip() == "---":
            break
        if each_line.startswith("paths:"):
            is_in_paths = True
            continue
        if is_in_paths:
            if each_line.startswith(" ") or each_line.startswith("\t"):
                stripped_path = each_line.strip().lstrip("-").strip().strip('"').strip("'")
                if stripped_path:
                    all_paths.append(stripped_path)
            else:
                is_in_paths = False
    return ",".join(all_paths) if all_paths else None


def _require_paths_glob(rule_file: Path) -> str | None:
    """Return the path glob for an optional rule, requiring frontmatter when it exists.

    Args:
        rule_file: The Claude rule file whose frontmatter may declare `paths:`.

    Returns:
        The comma-separated glob string, or None when the rule file is absent.

    Raises:
        AssertionError: When the rule file exists but declares no `paths:`
            frontmatter, which would silently disable the rule in Cursor.
    """
    if not rule_file.is_file():
        return None
    paths_glob = _read_paths_glob(rule_file)
    assert paths_glob is not None, (
        f"{rule_file.name}: path-scoped rule exists but declares no `paths:` frontmatter; "
        "add a `paths:` list or remove the file"
    )
    return paths_glob


def _always_apply_mappings(rules_directory: Path, docs_directory: Path) -> tuple[RuleMapping, ...]:
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


def _path_scoped_mappings(rules_directory: Path, docs_directory: Path) -> tuple[RuleMapping, ...]:
    return (
        RuleMapping(
            "tasklings-preferences",
            (rules_directory / "tasklings-preferences.md",),
            "tasklings-preferences.mdc",
            False,
            _require_paths_glob(rules_directory / "tasklings-preferences.md"),
            "Tasklings: Prefer / Do / Always engineering preferences (scoped path)",
            "verbatim",
            True,
        ),
        RuleMapping(
            "test-quality",
            (rules_directory / "testing.md", docs_directory / "TEST_QUALITY.md"),
            "test-quality.mdc",
            False,
            _require_paths_glob(rules_directory / "testing.md"),
            "Testing quality for test files",
            "merge_test_quality",
        ),
    )


def build_mappings(claude: Path) -> tuple[RuleMapping, ...]:
    """Resolve every rule into a concrete Cursor mapping against a Claude layout.

    Args:
        claude: The Claude layout root holding the `rules` and `docs` directories.

    Returns:
        One RuleMapping per rule, each path-scoped rule carrying a glob derived
        from its source rule's `paths:` frontmatter.
    """
    rules_directory = claude / "rules"
    docs_directory = claude / "docs"
    all_mappings = (
        *_always_apply_mappings(rules_directory, docs_directory),
        *_path_scoped_mappings(rules_directory, docs_directory),
    )
    mapping_by_key = {each_mapping.key: each_mapping for each_mapping in all_mappings}
    assert set(mapping_by_key) == set(_merged_mapping_key_order)
    return tuple(mapping_by_key[each_key] for each_key in _merged_mapping_key_order)
