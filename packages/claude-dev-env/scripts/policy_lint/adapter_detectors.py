from __future__ import annotations

from collections.abc import Iterable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path, PurePosixPath

from . import adapter_support
from .config import constants
from .model import Diagnostic, Document, DocumentSet, Location, SelectionKind, Severity


def _terminology_diagnostic(finding: str) -> Diagnostic:
    finding_match = constants.TERMINOLOGY_FINDING_PATTERN.fullmatch(finding)
    if finding_match is None:
        raise ValueError(finding)
    return Diagnostic(
        constants.TERMINOLOGY_SWEEP_RULE_ID,
        Severity.ERROR,
        finding_match.group(constants.TERMINOLOGY_MESSAGE_GROUP),
        Location(
            PurePosixPath(finding_match.group(constants.TERMINOLOGY_PATH_GROUP)),
            int(finding_match.group(constants.TERMINOLOGY_LINE_NUMBER_GROUP)),
        ),
    )


def terminology_diagnostics(
    document_set: DocumentSet,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Report staged prose terms that near-miss introduced identifiers.

    Args:
        document_set: Candidate staged documents and repository root.
        load_module: Shared script module loader.

    Returns:
        Source-located terminology diagnostics for the staged diff.
    """
    if document_set.selection is not SelectionKind.STAGED:
        return ()
    terminology_module = load_module(constants.TERMINOLOGY_SWEEP_MODULE_NAME)
    helper_stdout = StringIO()
    helper_stderr = StringIO()
    with redirect_stdout(helper_stdout), redirect_stderr(helper_stderr):
        all_findings = terminology_module.strict_staged_terminology_findings(
            document_set.repository_root
        )
    return tuple(_terminology_diagnostic(each_finding) for each_finding in all_findings)


def _stable_validator_message(document: Document, raw_message: str) -> str:
    _prefix, path_separator, message_tail = raw_message.partition(document.path.name)
    if not path_separator or not message_tail.startswith(":"):
        return raw_message
    return f"{document.path.as_posix()}{message_tail}"


def _validator_messages(
    document: Document, did_pass: bool, printed_text: str
) -> tuple[str, ...]:
    if did_pass:
        return ()
    return tuple(
        _stable_validator_message(document, each_line)
        for each_line in printed_text.splitlines()
        if each_line.strip()
    )


def _messages_for_validator_outcomes(
    document: Document, all_validator_outcomes: Iterable[object]
) -> tuple[str, ...]:
    return tuple(
        each_message
        for each_outcome in all_validator_outcomes
        for each_message in _validator_messages(
            document,
            bool(vars(each_outcome)["passed"]),
            str(vars(each_outcome)["output"]),
        )
    )


def validator_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the fast validator set on one document.

    Args:
        document: Current source text and path.
        repository_root: Request repository root for configuration resolution.
        load_module: Hook module loader.

    Returns:
        Path-normalized diagnostics for failed validators.
    """
    absolute_path = adapter_support._document_path(repository_root, document)
    validator_module = load_module("validators.run_all_validators")
    all_validator_outcomes = validator_module.validate_proposed_file(
        absolute_path.as_posix(),
        document.text,
        config_source_path=absolute_path,
        include_ruff=False,
        excluded_validator_names=constants.ALL_OVERLAPPING_VALIDATOR_NAMES,
    )
    all_messages = _messages_for_validator_outcomes(document, all_validator_outcomes)
    return adapter_support._diagnostics_for_messages(document, "validators", all_messages)


def code_rule_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the code-rule engine on one document.

    Args:
        document: Current text and optional prior text.
        repository_root: Request repository root for sibling-file resolution.
        load_module: Hook module loader.

    Returns:
        Diagnostics from the code-rule engine.
    """
    absolute_path = adapter_support._document_path(repository_root, document)
    legacy_module = load_module("blocking.code_rules_enforcer")
    legacy_stdout = StringIO()
    legacy_stderr = StringIO()
    with redirect_stdout(legacy_stdout), redirect_stderr(legacy_stderr):
        all_messages = legacy_module.validate_content_for_full_gate(
            document.text,
            absolute_path.as_posix(),
            old_content=document.prior_text or "",
            defer_scope_to_caller=True,
            sibling_directory=absolute_path.parent,
            include_comment_policy=True,
        )
    return adapter_support._diagnostics_for_messages(document, "code-rules", all_messages)


def state_description_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the state-description detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        State-description diagnostics.
    """
    absolute_path = adapter_support._document_path(repository_root, document)
    detector_module = load_module("blocking.state_description_blocker")
    all_messages = detector_module.find_violations(
        document.text, absolute_path.as_posix()
    )
    return adapter_support._diagnostics_for_state_messages(document, all_messages)


def plain_language_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the stored-prose detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        Plain-language diagnostics.
    """
    adapter_support._document_path(repository_root, document)
    detector_module = load_module("blocking.plain_language_blocker")
    all_matches = detector_module.find_banned_terms(document.text)
    all_messages = [f"Banned prose term: {each_term}" for each_term, _ in all_matches]
    return adapter_support._diagnostics_for_messages(document, "plain-language", all_messages)


def docstring_gate_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the docstring gate-count detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        Docstring gate diagnostics.
    """
    absolute_path = adapter_support._document_path(repository_root, document)
    detector_module = load_module("blocking.docstring_rule_gate_count_blocker")
    if not detector_module.is_target_rule_file(absolute_path.as_posix()):
        return ()
    all_messages = detector_module.find_gate_count_drift(document.text)
    return adapter_support._diagnostics_for_messages(document, "docstring-gate-count", all_messages)


def workflow_substitution_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the workflow substitution detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        Workflow substitution diagnostics.
    """
    adapter_support._document_path(repository_root, document)
    detector_module = load_module("blocking.workflow_substitution_slot_blocker")
    if not detector_module.content_has_violation(document.text):
        return ()
    return adapter_support._diagnostics_for_messages(
        document, "workflow-substitution", ("Workflow substitution slot is incomplete",)
    )


def rmtree_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the Windows cleanup detectors on one document.

    Args:
        document: Current text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        Cleanup safety diagnostics.
    """
    absolute_path = adapter_support._document_path(repository_root, document)
    unsafe_module = load_module("blocking.windows_rmtree_blocker")
    duplicate_module = load_module("blocking.duplicate_rmtree_helper_blocker")
    all_messages: list[str] = []
    if unsafe_module.payload_contains_unsafe_rmtree(document.text):
        all_messages.append("Unsafe rmtree ignore_errors usage")
    if (
        not duplicate_module.path_is_exempt(absolute_path.as_posix())
        and duplicate_module.payload_defines_sanctioned_helper(document.text)
    ):
        all_messages.append("Duplicate sanctioned rmtree helper")
    return adapter_support._diagnostics_for_messages(document, "rmtree-safety", all_messages)


def subprocess_budget_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the subprocess budget detector on one document.

    Args:
        document: Current text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        Subprocess budget diagnostics.
    """
    adapter_support._document_path(repository_root, document)
    detector_module = load_module("blocking.subprocess_budget_completeness")
    maybe_issue = detector_module.find_undercounted_budget(document.text)
    if maybe_issue is None:
        return ()
    function_name, all_omitted_counts = maybe_issue
    message = f"Subprocess budget omits counts in {function_name}: {sorted(all_omitted_counts)}"
    return adapter_support._diagnostics_for_messages(document, "subprocess-budget", (message,))


def hook_prose_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the hook-prose consistency detector on one document.

    Args:
        document: Current text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        Hook-prose diagnostics.
    """
    absolute_path = adapter_support._document_path(repository_root, document)
    detector_module = load_module("blocking.hook_prose_detector_consistency")
    if not detector_module.is_hook_python_module(absolute_path.as_posix()):
        return ()
    if not detector_module.content_has_violation(
        document.text, absolute_path.as_posix()
    ):
        return ()
    return adapter_support._diagnostics_for_messages(
        document,
        "hook-prose-consistency",
        ("Hook prose detector does not match its output contract",),
    )


def open_question_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Run the open-question plan detector on one document.

    Args:
        document: Current plan text.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        Plan question diagnostics.
    """
    adapter_support._document_path(repository_root, document)
    detector_module = load_module("blocking.open_questions_in_plans_blocker")
    if not detector_module._content_has_open_questions(document.text):
        return ()
    return adapter_support._diagnostics_for_messages(
        document, "open-questions", ("Plan contains an open question",)
    )


def hook_format_diagnostics(
    document: Document,
    repository_root: Path,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Check one settings document for a nonportable hook command.

    Args:
        document: Current settings text and path.
        repository_root: Request repository root for document-path resolution.
        load_module: Hook module loader.

    Returns:
        A diagnostic when the command uses a home-relative Python script path.
    """
    adapter_support._document_path(repository_root, document)
    detector_module = load_module("validation.hook_format_validator")
    if detector_module.SIMPLE_PATTERN.search(document.text) is None:
        return ()
    return adapter_support._diagnostics_for_messages(
        document,
        "hook-format",
        ("Hook command uses a home-relative Python script path",),
    )
