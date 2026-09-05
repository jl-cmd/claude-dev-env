from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath

from . import adapters, model


def build_document_rule(
    rule_id: str,
    accepts: Callable[[model.Document], bool],
    check: model.DocumentChecker,
) -> model.DocumentRule:
    """Build a document rule for changed and repository selections.

    Args:
        rule_id: Stable rule identifier.
        accepts: Predicate for documents handled by the rule.
        check: Pure document checker.

    Returns:
        A configured document rule.
    """
    return model.DocumentRule(
        rule_id, frozenset({"changed", "repository"}), accepts, check
    )


def repository_path_diagnostics(
    document_set: model.DocumentSet,
) -> tuple[model.Diagnostic, ...]:
    """Report tracked paths that differ only by case.

    Args:
        document_set: Repository documents to compare.

    Returns:
        Path collision diagnostics.
    """
    path_by_lower_name: dict[str, PurePosixPath] = {}
    all_diagnostics: list[model.Diagnostic] = []
    for each_document in document_set.documents:
        lower_name = each_document.path.as_posix().lower()
        previous_path = path_by_lower_name.get(lower_name)
        if previous_path is not None and previous_path != each_document.path:
            all_diagnostics.append(
                model.Diagnostic(
                    "repository-path-collision",
                    model.Severity.ERROR,
                    f"Repository paths differ only by case: {previous_path}",
                    model.Location(each_document.path, 1, 1),
                )
            )
        path_by_lower_name[lower_name] = each_document.path
    return tuple(all_diagnostics)


def _python_document_rules() -> tuple[model.Rule, ...]:
    return (
        build_document_rule(
            "validators", adapters.accepts_python, adapters.validator_diagnostics
        ),
        build_document_rule(
            "code-rules", adapters.accepts_code, adapters.code_rule_diagnostics
        ),
        build_document_rule(
            "docstring-gate-count",
            adapters.accepts_markdown,
            adapters.docstring_gate_diagnostics,
        ),
        build_document_rule(
            "rmtree-safety", adapters.accepts_python, adapters.rmtree_diagnostics
        ),
        build_document_rule(
            "subprocess-budget",
            adapters.accepts_python,
            adapters.subprocess_budget_diagnostics,
        ),
        build_document_rule(
            "hook-prose-consistency",
            adapters.accepts_python,
            adapters.hook_prose_diagnostics,
        ),
    )


def _text_document_rules() -> tuple[model.Rule, ...]:
    return (
        build_document_rule(
            "state-description",
            adapters.accepts_source_or_markdown,
            adapters.state_description_diagnostics,
        ),
        build_document_rule(
            "plain-language",
            adapters.accepts_stored_prompt,
            adapters.plain_language_diagnostics,
        ),
        build_document_rule(
            "open-questions", adapters.accepts_plans, adapters.open_question_diagnostics
        ),
        build_document_rule(
            "workflow-substitution",
            adapters.accepts_workflow,
            adapters.workflow_substitution_diagnostics,
        ),
    )


def _configuration_document_rules() -> tuple[model.Rule, ...]:
    return (
        build_document_rule(
            "hook-configuration",
            adapters.accepts_hook_configuration,
            adapters.hook_configuration_diagnostics,
        ),
        build_document_rule(
            "hook-format",
            adapters.accepts_hook_format,
            adapters.hook_format_diagnostics,
        ),
    )


def default_registry() -> tuple[model.Rule, ...]:
    """Return the default policy rules in a fixed order.

    Returns:
        The default policy rules.
    """
    return (
        *_python_document_rules(),
        *_text_document_rules(),
        *_configuration_document_rules(),
        model.ChangeSetRule(
            "test-pairing",
            frozenset({"changed"}),
            frozenset({model.SelectionKind.STAGED, model.SelectionKind.BASE}),
            adapters.test_pairing_diagnostics,
        ),
        model.ChangeSetRule(
            "terminology-sweep",
            frozenset({"changed"}),
            frozenset({model.SelectionKind.STAGED, model.SelectionKind.BASE}),
            adapters.terminology_diagnostics,
        ),
        model.RepositoryRule(
            "repository-path-collision",
            frozenset({"repository"}),
            repository_path_diagnostics,
        ),
    )


def selected_rules(
    all_rules: tuple[model.Rule, ...], all_rule_sets: frozenset[str]
) -> tuple[model.Rule, ...]:
    """Select rules that belong to one requested rule set.

    Args:
        all_rules: Candidate registry entries.
        all_rule_sets: Rule sets requested by the caller.

    Returns:
        Matching rules in registry order.
    """
    return tuple(
        each_rule
        for each_rule in all_rules
        if each_rule.rule_sets.intersection(all_rule_sets)
    )
