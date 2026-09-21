"""The contrast-framing rule reaches authored Markdown through the registry."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from policy_lint import adapter_contrast_framing, registry
from policy_lint.model import ContentOrigin, Document, DocumentRule

_RULE_ID = "contrast-framing"
_DOCUMENT_PATH = "packages/claude-dev-env/rules/example.md"


def _document(prose: str, path: str = _DOCUMENT_PATH) -> Document:
    return Document(
        PurePosixPath(path),
        prose,
        None,
        None,
        ContentOrigin.WORKTREE,
    )


def _messages_for(prose: str, repository_root: Path) -> tuple[str, ...]:
    all_diagnostics = adapter_contrast_framing.contrast_framing_diagnostics(
        _document(prose), repository_root
    )
    return tuple(each_diagnostic.message for each_diagnostic in all_diagnostics)


def _registered_rule() -> DocumentRule:
    for each_rule in registry.default_registry():
        if each_rule.rule_id == _RULE_ID and isinstance(each_rule, DocumentRule):
            return each_rule
    raise AssertionError(_RULE_ID)


def test_the_rule_is_registered_for_changed_and_repository_selections() -> None:
    contrast_rule = _registered_rule()

    assert contrast_rule.rule_sets == frozenset({"changed", "repository"})


def test_a_contrast_sentence_reports_with_its_location(tmp_path: Path) -> None:
    all_diagnostics = adapter_contrast_framing.contrast_framing_diagnostics(
        _document("Heading line.\nOne answer, not two.\n"), tmp_path
    )

    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].rule_id == _RULE_ID
    assert all_diagnostics[0].location.start_line == 2
    assert "trailing-comma-not" in all_diagnostics[0].message


def test_a_statement_of_what_is_passes(tmp_path: Path) -> None:
    assert _messages_for("The check names the failing line.\n", tmp_path) == ()


def test_the_rule_accepts_authored_markdown_and_skips_the_changelog() -> None:
    contrast_rule = _registered_rule()

    assert contrast_rule.accepts(_document("text\n"))
    assert not contrast_rule.accepts(
        _document("text\n", "packages/claude-dev-env/CHANGELOG.md")
    )
    assert not contrast_rule.accepts(
        _document("text\n", "packages/claude-dev-env/scripts/tool.py")
    )
