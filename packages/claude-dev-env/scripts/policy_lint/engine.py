from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from .model import (
    ChangeSetRule,
    Diagnostic,
    Document,
    DocumentRule,
    DocumentSet,
    LintReport,
    LintRequest,
    RepositoryRule,
    Rule,
    SelectionKind,
)
from .registry import default_registry, selected_rules
from .selection import select_documents


def lint(
    request: LintRequest,
    all_registry: Sequence[Rule] | None = None,
) -> LintReport:
    """Run the selected rules on one source selection.

    Args:
        request: Repository root, source, and rule sets.
        all_registry: Optional registry replacement.

    Returns:
        A report of diagnostics and rule execution state.
    """
    document_set = select_documents(request)
    candidate_rules = tuple(all_registry) if all_registry is not None else default_registry()
    selected = selected_rules(candidate_rules, request.rule_sets)
    all_diagnostics, executed, failed, skipped = _run_selected_rules(selected, document_set)
    return LintReport(
        1,
        tuple(sorted(all_diagnostics, key=_diagnostic_sort_key)),
        tuple(each_document.path for each_document in document_set.documents),
        executed,
        failed,
        skipped,
    )


def _run_selected_rules(
    all_rules: tuple[Rule, ...], document_set: DocumentSet
) -> tuple[list[Diagnostic], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    resolved_repository_root = document_set.repository_root.resolve()
    all_diagnostics: list[Diagnostic] = []
    all_executed_rules: list[str] = []
    all_failed_rules: list[str] = []
    all_skipped_rules: list[str] = []
    for each_rule in all_rules:
        _run_rule(
            each_rule,
            document_set,
            resolved_repository_root,
            all_diagnostics,
            all_executed_rules,
            all_failed_rules,
            all_skipped_rules,
        )
    return (
        all_diagnostics,
        tuple(all_executed_rules),
        tuple(all_failed_rules),
        tuple(all_skipped_rules),
    )


def _run_rule(
    rule: Rule,
    document_set: DocumentSet,
    resolved_repository_root: Path,
    all_diagnostics: list[Diagnostic],
    all_executed_rules: list[str],
    all_failed_rules: list[str],
    all_skipped_rules: list[str],
) -> None:
    pending_diagnostics: list[Diagnostic] = []
    all_skipped_before = len(all_skipped_rules)
    if _rule_execution_failed(
        rule,
        document_set,
        resolved_repository_root,
        pending_diagnostics,
        all_skipped_rules,
    ):
        all_failed_rules.append(rule.rule_id)
        return
    if len(all_skipped_rules) != all_skipped_before:
        return
    all_diagnostics.extend(pending_diagnostics)
    all_executed_rules.append(rule.rule_id)


def _rule_execution_failed(
    rule: Rule,
    document_set: DocumentSet,
    resolved_repository_root: Path,
    all_diagnostics: list[Diagnostic],
    all_skipped_rules: list[str],
) -> bool:
    try:
        _execute_rule(
            rule,
            document_set,
            resolved_repository_root,
            all_diagnostics,
            all_skipped_rules,
        )
    except (
        AttributeError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        SyntaxError,
        TypeError,
        UnicodeError,
        ValueError,
    ):
        return True
    return False


def _execute_rule(
    rule: Rule,
    document_set: DocumentSet,
    resolved_repository_root: Path,
    all_diagnostics: list[Diagnostic],
    all_skipped_rules: list[str],
) -> None:
    if isinstance(rule, DocumentRule):
        _run_document_rule(
            rule,
            document_set,
            resolved_repository_root,
            all_diagnostics,
            all_skipped_rules,
        )
        return
    if isinstance(rule, ChangeSetRule):
        _run_changeset_rule(rule, document_set, all_diagnostics, all_skipped_rules)
        return
    _run_repository_rule(rule, document_set, all_diagnostics, all_skipped_rules)


def _run_document_rule(
    rule: DocumentRule,
    document_set: DocumentSet,
    resolved_repository_root: Path,
    all_diagnostics: list[Diagnostic],
    all_skipped_rules: list[str],
) -> None:
    all_documents = tuple(
        each_document
        for each_document in document_set.documents
        if rule.accepts(each_document)
    )
    if not all_documents:
        all_skipped_rules.append(rule.rule_id)
        return
    for each_document in all_documents:
        all_diagnostics.extend(
            _scoped_diagnostics(
                rule.check(each_document, resolved_repository_root),
                each_document,
            )
        )


def _run_changeset_rule(
    rule: ChangeSetRule,
    document_set: DocumentSet,
    all_diagnostics: list[Diagnostic],
    all_skipped_rules: list[str],
) -> None:
    if document_set.selection not in rule.selections:
        all_skipped_rules.append(rule.rule_id)
        return
    all_diagnostics.extend(rule.check(document_set))


def _run_repository_rule(
    rule: RepositoryRule,
    document_set: DocumentSet,
    all_diagnostics: list[Diagnostic],
    all_skipped_rules: list[str],
) -> None:
    if document_set.selection is not SelectionKind.REPOSITORY:
        all_skipped_rules.append(rule.rule_id)
        return
    all_diagnostics.extend(rule.check(document_set))


def _scoped_diagnostics(
    all_diagnostics: Iterable[Diagnostic],
    document: Document,
) -> tuple[Diagnostic, ...]:
    if document.changed_lines is None or not document.changed_lines:
        return tuple(all_diagnostics)
    return tuple(
        each_diagnostic
        for each_diagnostic in all_diagnostics
        if each_diagnostic.location is None
        or each_diagnostic.location.start_line in document.changed_lines
    )


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, int, int, str, str]:
    if diagnostic.location is None:
        return ("", 0, 0, diagnostic.rule_id, diagnostic.message)
    return (
        diagnostic.location.path.as_posix(),
        diagnostic.location.start_line,
        diagnostic.location.start_column,
        diagnostic.rule_id,
        diagnostic.message,
    )
