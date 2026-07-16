"""Validates repo-relative doc cross-references resolve to real files.

Bot reviewers on PR #257 caught hook_log_init.py:69 referencing
`commands/hook-log-init.md` when the actual path is
`packages/claude-dev-env/commands/hook-log-init.md`. PR #232 had a
similar /qbug doc reference that didn't match the gate's invocation.

This test walks Python docstrings and Markdown files for repo-relative
path references, then confirms each one resolves on disk. The matcher
is intentionally narrow (no false positives on URLs, regex examples,
or pseudo-code snippets) and exposes an ALLOWED_MISSING set for paths
that legitimately don't exist (e.g., illustrative examples).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


REPOSITORY_ROOT: Path = Path(__file__).resolve().parent.parent

PATH_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
    r"`(?P<path>(?:packages|tests|scripts|docs|config|\.claude|\.cursor)/[A-Za-z0-9_./-]+\.(?:py|md|json|yaml|yml|toml|cfg|sh|ps1))`"
)

DIRECTORIES_TO_SCAN: tuple[str, ...] = ("packages", "docs", "tests", "scripts")
DIRECTORIES_TO_SKIP: frozenset[str] = frozenset(
    {".git", "__pycache__", "node_modules", ".venv", "venv", ".claude", ".pytest_cache"}
)
MAX_DETAIL_LINES_IN_FAILURE: int = 50

ALLOWED_MISSING_PATHS: frozenset[str] = frozenset(
    {
        ".cursor/agents/clean-coder.md",
        "config/local-identity.json",
        "config/sweep_config.py",
        "config/timing.py",
        "config/constants.py",
        "config/selectors.py",
        ".claude/CLAUDE.md",
        ".claude/plain-language-allow.json",
        ".claude/settings.json",
        "docs/.claude-notes.md",
        "docs/file1.md",
        "docs/file2.md",
        "packages/agent-gate-claude/hooks/gate_enforcer.py",
        "packages/agent-gate-claude/hooks/gate_trigger.py",
        "packages/agent-gate-claude/src/agent_gate_claude/config/constants.py",
        "packages/agent-gate-core/src/agent_gate_core/config/constants.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/assessment_models.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/canonical_prompt_builder.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/config/constants.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/server.py",
        "packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1",
        "packages/claude-dev-env/scripts/config/sweep_config.py",
        "packages/claude-dev-env/scripts/sweep_empty_dirs.py",
        "packages/claude-dev-env/scripts/tests/test_sweep_empty_dirs.py",
        "scripts/README.md",
        "scripts/bugteam_code_rules_gate.py",
        "scripts/cluster_recurrences.py",
        "scripts/collect_log_window.py",
        "scripts/config/notes_constants.py",
        "scripts/db/config.py",
        "scripts/discover_open_prs.py",
        "scripts/grant_project_claude_permissions.py",
        "scripts/logifix.ps1",
        "scripts/mine_copilot_findings.py",
        "scripts/revoke_project_claude_permissions.py",
        "scripts/stp_selection.py",
        "scripts/test_groq_bugteam.py",
        "tests/data/test_x.py",
        "tests/test_sweep_empty_dirs.py",
    }
)


def _iter_repo_files(extension: str) -> list[Path]:
    matched_files: list[Path] = []
    for each_top_directory in DIRECTORIES_TO_SCAN:
        each_top_path = REPOSITORY_ROOT / each_top_directory
        if not each_top_path.exists():
            continue
        for each_path in each_top_path.rglob(f"*{extension}"):
            relative_path_parts = each_path.relative_to(REPOSITORY_ROOT).parts
            if any(part in DIRECTORIES_TO_SKIP for part in relative_path_parts):
                continue
            matched_files.append(each_path)
    return matched_files


def _extract_docstring_texts(python_file_path: Path) -> list[str]:
    try:
        source_text = python_file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        parsed_tree = ast.parse(source_text)
    except SyntaxError:
        return []
    docstring_owner_types = (
        ast.Module,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    collected_docstrings: list[str] = []
    for each_node in ast.walk(parsed_tree):
        if not isinstance(each_node, docstring_owner_types):
            continue
        each_docstring = ast.get_docstring(each_node)
        if each_docstring is not None:
            collected_docstrings.append(each_docstring)
    return collected_docstrings


def _references_in_text(text_to_scan: str) -> set[str]:
    return {
        each_match.group("path")
        for each_match in PATH_REFERENCE_PATTERN.finditer(text_to_scan)
    }


def _reference_exists_on_disk(
    reference: str, *, source_file: Path | None = None
) -> bool:
    if (REPOSITORY_ROOT / reference).exists():
        return True
    if not reference.startswith("packages/"):
        packaged_path = REPOSITORY_ROOT / "packages" / "claude-dev-env" / reference
        if packaged_path.exists():
            return True
    if source_file is not None:
        for each_directory in (source_file.parent, *source_file.parents):
            if (each_directory / reference).exists():
                return True
            if each_directory == REPOSITORY_ROOT:
                break
    return False


def _missing_references_for_python_files() -> dict[str, set[str]]:
    missing_by_source_file: dict[str, set[str]] = {}
    for each_python_file in _iter_repo_files(".py"):
        for each_docstring in _extract_docstring_texts(each_python_file):
            for each_reference in _references_in_text(each_docstring):
                if each_reference in ALLOWED_MISSING_PATHS:
                    continue
                if _reference_exists_on_disk(each_reference, source_file=each_python_file):
                    continue
                relative_source_path = each_python_file.relative_to(
                    REPOSITORY_ROOT
                ).as_posix()
                missing_by_source_file.setdefault(relative_source_path, set()).add(
                    each_reference
                )
    return missing_by_source_file


def _missing_references_for_markdown_files() -> dict[str, set[str]]:
    missing_by_source_file: dict[str, set[str]] = {}
    for each_markdown_file in _iter_repo_files(".md"):
        try:
            each_text = each_markdown_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for each_reference in _references_in_text(each_text):
            if each_reference in ALLOWED_MISSING_PATHS:
                continue
            if _reference_exists_on_disk(each_reference, source_file=each_markdown_file):
                continue
            relative_source_path = each_markdown_file.relative_to(
                REPOSITORY_ROOT
            ).as_posix()
            missing_by_source_file.setdefault(relative_source_path, set()).add(
                each_reference
            )
    return missing_by_source_file


def _format_missing_for_failure(missing_by_source_file: dict[str, set[str]]) -> str:
    detail_lines: list[str] = []
    for each_source_file in sorted(missing_by_source_file):
        for each_reference in sorted(missing_by_source_file[each_source_file]):
            detail_lines.append(f"  {each_source_file} -> {each_reference}")
            if len(detail_lines) >= MAX_DETAIL_LINES_IN_FAILURE:
                detail_lines.append(
                    f"  ... and more (capped at {MAX_DETAIL_LINES_IN_FAILURE})"
                )
                return "\n".join(detail_lines)
    return "\n".join(detail_lines)


def test_python_docstrings_reference_existing_repo_paths() -> None:
    missing_by_source_file = _missing_references_for_python_files()
    assert missing_by_source_file == {}, (
        "Python docstrings reference repo paths that do not exist on disk. "
        "Either fix the path or, if it is illustrative only, add it to "
        "ALLOWED_MISSING_PATHS in this test:\n"
        + _format_missing_for_failure(missing_by_source_file)
    )


def test_markdown_files_reference_existing_repo_paths() -> None:
    missing_by_source_file = _missing_references_for_markdown_files()
    assert missing_by_source_file == {}, (
        "Markdown files reference repo paths that do not exist on disk. "
        "Either fix the path or, if it is illustrative only, add it to "
        "ALLOWED_MISSING_PATHS in this test:\n"
        + _format_missing_for_failure(missing_by_source_file)
    )


def test_pattern_matches_known_repo_relative_path() -> None:
    sample_text = (
        "See `packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py` for details."
    )
    references = _references_in_text(sample_text)
    assert "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py" in references, (
        f"Matcher must recognize a real repo path in backticks, got: {references}"
    )


def test_pattern_ignores_external_url() -> None:
    sample_text = "Read https://example.com/path/to/file.py for context."
    references = _references_in_text(sample_text)
    assert references == set(), (
        f"Matcher must not pick up unbacked URLs, got: {references}"
    )


def test_pattern_ignores_non_repo_top_level_directory() -> None:
    sample_text = "Generated under `tmp/build/output.py` during the run."
    references = _references_in_text(sample_text)
    assert references == set(), (
        f"Matcher must not pick up paths outside the configured top-level dirs, got: {references}"
    )


def test_pattern_detects_synthetic_missing_reference() -> None:
    sample_text = "Refer to `packages/this/path/does/not/exist.py` for the implementation."
    references = _references_in_text(sample_text)
    candidate = "packages/this/path/does/not/exist.py"
    assert candidate in references, f"Matcher must extract the candidate, got: {references}"
    assert not (REPOSITORY_ROOT / candidate).exists(), (
        "Synthetic path must not actually exist, otherwise the assertion is vacuous"
    )


def test_iter_repo_files_finds_files_when_repo_path_contains_skip_segment() -> None:
    found_python_files = _iter_repo_files(".py")
    assert len(found_python_files) > 0, (
        "_iter_repo_files must return matches even when REPOSITORY_ROOT's "
        "absolute path contains a segment listed in DIRECTORIES_TO_SKIP "
        "(e.g., a checkout under '.../.claude/worktrees/...' or '.../venv/...'). "
        "Skip filtering must apply to repo-internal segments only."
    )


AUTOCONVERGE_SKILL_MD: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "skills"
    / "autoconverge"
    / "SKILL.md"
)
AUTOCONVERGE_CONVERGENCE_MD: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "skills"
    / "autoconverge"
    / "reference"
    / "convergence.md"
)
AUTOCONVERGE_CONVERGE_MJS: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "skills"
    / "autoconverge"
    / "workflow"
    / "converge.mjs"
)
SELECT_CONVERGE_PACER_SCRIPT: str = "select_converge_pacer.py"
PACER_PORTABLE_TOKEN: str = "pacer=portable"
DO_NOT_ABORT_WORKFLOW_MISSING_PHRASE: str = (
    "Do not abort** because the Workflow tool is missing"
)
PORTABLE_DRIVER_DOC_NAME: str = "portable-driver.md"
RUN_CODE_REVIEW_LENS_SIGNATURE: str = "function runCodeReviewLens"
CODE_QUALITY_AGENT_TYPE: str = "code-quality-agent"
REPORT_ONLY_CONFIG_PHRASE: str = (
    "report-only workflow agent — see runCodeReviewLens in "
    "workflow/converge.mjs for its configuration"
)
REVIEW_LENS_BOUNDARY_HEADING: str = "## Review-lens boundary"
CODE_REVIEW_LENS_BULLET: str = "**Code-review lens**"
LINE_NUMBER_CITATION_PATTERN: re.Pattern[str] = re.compile(
    r"(?:SKILL\.md|workflow/converge\.mjs):\d+"
)
RELATIVE_MARKDOWN_LINK_PATTERN: re.Pattern[str] = re.compile(
    r"\((?P<relative>(?!https?://|#)[A-Za-z0-9_./-]+\.md)\)"
)


def _function_body_named(source: str, signature: str) -> str:
    """Return the brace-delimited body of the first function matching signature.

    Parses by symbol and brace depth only — never by line number.
    """
    signature_at = source.find(signature)
    assert signature_at >= 0, f"source must declare {signature!r}"
    opening_brace_at = source.find("{", signature_at)
    assert opening_brace_at >= 0, f"{signature!r} must open a function body with '{{'"
    depth = 0
    for each_offset, each_character in enumerate(
        source[opening_brace_at:], start=opening_brace_at
    ):
        if each_character == "{":
            depth += 1
        elif each_character == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace_at : each_offset + 1]
    raise AssertionError(f"{signature!r} body never closed its opening brace")


def _relative_markdown_links_in(markdown_text: str) -> list[str]:
    return [
        each_match.group("relative")
        for each_match in RELATIVE_MARKDOWN_LINK_PATTERN.finditer(markdown_text)
    ]


def test_autoconverge_skill_documents_review_lens_boundary() -> None:
    skill_text = AUTOCONVERGE_SKILL_MD.read_text(encoding="utf-8")
    convergence_text = AUTOCONVERGE_CONVERGENCE_MD.read_text(encoding="utf-8")

    assert SELECT_CONVERGE_PACER_SCRIPT in skill_text, (
        "SKILL.md Requirements must name the pacer selection helper "
        f"({SELECT_CONVERGE_PACER_SCRIPT!r})"
    )
    assert PACER_PORTABLE_TOKEN in skill_text, (
        "SKILL.md Requirements must document the portable pacer branch "
        f"({PACER_PORTABLE_TOKEN!r})"
    )
    assert DO_NOT_ABORT_WORKFLOW_MISSING_PHRASE in skill_text, (
        "SKILL.md Requirements must forbid aborting solely for a missing "
        f"Workflow tool ({DO_NOT_ABORT_WORKFLOW_MISSING_PHRASE!r})"
    )
    assert PORTABLE_DRIVER_DOC_NAME in skill_text, (
        "SKILL.md must link the shared portable driver protocol "
        f"({PORTABLE_DRIVER_DOC_NAME!r})"
    )
    assert "autoconverge requires the Workflow tool" not in skill_text, (
        "SKILL.md must not keep the abort-only Workflow-tool requirement"
    )

    assert AUTOCONVERGE_CONVERGE_MJS.is_file(), (
        f"converge.mjs must exist on disk: {AUTOCONVERGE_CONVERGE_MJS}"
    )
    converge_source = AUTOCONVERGE_CONVERGE_MJS.read_text(encoding="utf-8")
    assert RUN_CODE_REVIEW_LENS_SIGNATURE in converge_source, (
        f"converge.mjs must declare {RUN_CODE_REVIEW_LENS_SIGNATURE!r}"
    )
    code_review_lens_body = _function_body_named(
        converge_source, RUN_CODE_REVIEW_LENS_SIGNATURE
    )
    assert CODE_QUALITY_AGENT_TYPE in code_review_lens_body, (
        f"{RUN_CODE_REVIEW_LENS_SIGNATURE} body must name agentType "
        f"{CODE_QUALITY_AGENT_TYPE!r}; body was:\n{code_review_lens_body}"
    )

    assert REVIEW_LENS_BOUNDARY_HEADING in skill_text, (
        "SKILL.md must include a Review-lens boundary section"
    )
    assert "reference/convergence.md" in skill_text, (
        "SKILL.md Review-lens boundary must link to reference/convergence.md "
        "as the canonical home for the Code-review lens bullet"
    )
    assert CODE_REVIEW_LENS_BULLET in convergence_text, (
        "convergence.md must carry the canonical Code-review lens bullet"
    )
    assert "runCodeReviewLens" in convergence_text, (
        "convergence.md Code-review lens bullet must cite runCodeReviewLens by symbol"
    )
    assert REPORT_ONLY_CONFIG_PHRASE in convergence_text, (
        "convergence.md must state the report-only config pointer phrase "
        f"({REPORT_ONLY_CONFIG_PHRASE!r})"
    )
    assert CODE_QUALITY_AGENT_TYPE in convergence_text, (
        "convergence.md must name the code-review lens agent type "
        f"({CODE_QUALITY_AGENT_TYPE})"
    )

    skill_boundary_start = skill_text.index(REVIEW_LENS_BOUNDARY_HEADING)
    skill_boundary_end = skill_text.index("\n## ", skill_boundary_start + 1)
    skill_boundary_section = skill_text[skill_boundary_start:skill_boundary_end]

    code_review_bullet_at = convergence_text.index(CODE_REVIEW_LENS_BULLET)
    next_bullet_match = re.search(
        r"\n   - \*\*", convergence_text[code_review_bullet_at + 1 :]
    )
    if next_bullet_match is None:
        code_review_bullet_section = convergence_text[code_review_bullet_at:]
    else:
        code_review_bullet_section = convergence_text[
            code_review_bullet_at : code_review_bullet_at
            + 1
            + next_bullet_match.start()
        ]

    for each_doc_path, each_doc_text in (
        (AUTOCONVERGE_SKILL_MD, skill_text),
        (AUTOCONVERGE_CONVERGENCE_MD, convergence_text),
    ):
        line_citation_match = LINE_NUMBER_CITATION_PATTERN.search(each_doc_text)
        assert line_citation_match is None, (
            f"{each_doc_path.name} must not cite SKILL.md:<line> or "
            f"workflow/converge.mjs:<start>[-<end>]; found "
            f"{line_citation_match.group(0)!r}"
        )

    for each_section_label, each_section_text in (
        ("SKILL.md Review-lens boundary", skill_boundary_section),
        ("convergence.md Code-review lens bullet", code_review_bullet_section),
    ):
        lowered_section = each_section_text.lower()
        assert "opus" not in lowered_section, (
            f"{each_section_label} must not name model/effort config "
            f"('opus'); that fact lives in runCodeReviewLens"
        )
        assert "medium" not in lowered_section, (
            f"{each_section_label} must not name model/effort config "
            f"('medium'); that fact lives in runCodeReviewLens"
        )

    for each_relative_path in _relative_markdown_links_in(skill_boundary_section):
        resolved_from_skill = (
            AUTOCONVERGE_SKILL_MD.parent / each_relative_path
        ).resolve()
        assert resolved_from_skill.is_file(), (
            f"SKILL.md Review-lens boundary link must resolve on disk: "
            f"{each_relative_path} -> {resolved_from_skill}"
        )

    for each_relative_path in _relative_markdown_links_in(code_review_bullet_section):
        resolved_from_convergence = (
            AUTOCONVERGE_CONVERGENCE_MD.parent / each_relative_path
        ).resolve()
        assert resolved_from_convergence.is_file(), (
            f"convergence.md Code-review lens link must resolve on disk: "
            f"{each_relative_path} -> {resolved_from_convergence}"
        )
