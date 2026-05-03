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
        "config/timing.py",
        "config/constants.py",
        "config/selectors.py",
        ".claude/CLAUDE.md",
        ".claude/settings.json",
        "packages/agent-gate-claude/hooks/gate_enforcer.py",
        "packages/agent-gate-claude/hooks/gate_trigger.py",
        "packages/agent-gate-claude/src/agent_gate_claude/config/constants.py",
        "packages/agent-gate-core/src/agent_gate_core/config/constants.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/assessment_models.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/canonical_prompt_builder.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/config/constants.py",
        "packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/server.py",
        "packages/claude-dev-env/hooks/blocking/pwsh_enforcer.py",
        "scripts/README.md",
        "scripts/bugteam_code_rules_gate.py",
        "scripts/db/config.py",
        "scripts/discover_open_prs.py",
        "scripts/grant_project_claude_permissions.py",
        "scripts/logifix.ps1",
        "scripts/revoke_project_claude_permissions.py",
        "scripts/test_groq_bugteam.py",
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


def _missing_references_for_python_files() -> dict[str, set[str]]:
    missing_by_source_file: dict[str, set[str]] = {}
    for each_python_file in _iter_repo_files(".py"):
        for each_docstring in _extract_docstring_texts(each_python_file):
            for each_reference in _references_in_text(each_docstring):
                if each_reference in ALLOWED_MISSING_PATHS:
                    continue
                if (REPOSITORY_ROOT / each_reference).exists():
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
            if (REPOSITORY_ROOT / each_reference).exists():
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
        f"Synthetic path must not actually exist, otherwise the assertion is vacuous"
    )


def test_iter_repo_files_finds_files_when_repo_path_contains_skip_segment() -> None:
    found_python_files = _iter_repo_files(".py")
    assert len(found_python_files) > 0, (
        "_iter_repo_files must return matches even when REPOSITORY_ROOT's "
        "absolute path contains a segment listed in DIRECTORIES_TO_SKIP "
        "(e.g., a checkout under '.../.claude/worktrees/...' or '.../venv/...'). "
        "Skip filtering must apply to repo-internal segments only."
    )
