from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from . import adapter_configuration, adapter_detectors, adapter_pairing, adapter_support
from .config import constants
from .model import Diagnostic, Document, DocumentSet

_document_path = adapter_support._document_path
_line_number = adapter_support._line_number
_diagnostics_for_messages = adapter_support._diagnostics_for_messages
_source_line_for_phrase = adapter_support._source_line_for_phrase
_diagnostics_for_state_messages = adapter_support._diagnostics_for_state_messages


def _hooks_module(module_name: str) -> ModuleType:
    hooks_directory = str(Path(__file__).resolve().parents[1].parent / "hooks")
    if hooks_directory not in sys.path:
        sys.path.insert(0, hooks_directory)
    return importlib.import_module(module_name)


def _pr_loop_script_module(module_name: str) -> ModuleType:
    package_directory = Path(__file__).resolve().parent.parent.parent
    scripts_directory = str(
        package_directory.joinpath(*constants.ALL_PR_LOOP_SCRIPTS_PATH_SEGMENTS)
    )
    if scripts_directory not in sys.path:
        sys.path.insert(0, scripts_directory)
    return importlib.import_module(module_name)


def validator_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the fast validator set on one document.

    Args:
        document: Current source text and path.
        repository_root: Request repository root for configuration resolution.

    Returns:
        Path-normalized diagnostics for failed validators.
    """
    return adapter_detectors.validator_diagnostics(
        document, repository_root, _hooks_module
    )


def code_rule_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the code-rule engine on one document.

    Args:
        document: Current text and optional prior text.
        repository_root: Request repository root for sibling-file resolution.

    Returns:
        Diagnostics from the code-rule engine.
    """
    return adapter_detectors.code_rule_diagnostics(
        document, repository_root, _hooks_module
    )


def state_description_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the state-description detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        State-description diagnostics.
    """
    return adapter_detectors.state_description_diagnostics(
        document, repository_root, _hooks_module
    )


def plain_language_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the stored-prose detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Plain-language diagnostics.
    """
    return adapter_detectors.plain_language_diagnostics(
        document, repository_root, _hooks_module
    )


def docstring_gate_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the docstring gate-count detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Docstring gate diagnostics.
    """
    return adapter_detectors.docstring_gate_diagnostics(
        document, repository_root, _hooks_module
    )


def workflow_substitution_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the workflow substitution detector on one document.

    Args:
        document: Current document text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Workflow substitution diagnostics.
    """
    return adapter_detectors.workflow_substitution_diagnostics(
        document, repository_root, _hooks_module
    )


def rmtree_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the Windows cleanup detectors on one document.

    Args:
        document: Current text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Cleanup safety diagnostics.
    """
    return adapter_detectors.rmtree_diagnostics(
        document, repository_root, _hooks_module
    )


def subprocess_budget_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the subprocess budget detector on one document.

    Args:
        document: Current text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Subprocess budget diagnostics.
    """
    return adapter_detectors.subprocess_budget_diagnostics(
        document, repository_root, _hooks_module
    )


def hook_prose_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the hook-prose consistency detector on one document.

    Args:
        document: Current text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Hook-prose diagnostics.
    """
    return adapter_detectors.hook_prose_diagnostics(
        document, repository_root, _hooks_module
    )


def open_question_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Run the open-question plan detector on one document.

    Args:
        document: Current plan text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Plan question diagnostics.
    """
    return adapter_detectors.open_question_diagnostics(
        document, repository_root, _hooks_module
    )


def hook_configuration_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Check hook configuration for policy decision fields.

    Args:
        document: Current hook configuration text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Hook configuration diagnostics.
    """
    return adapter_configuration.hook_configuration_diagnostics(
        document, repository_root
    )


def test_pairing_diagnostics(document_set: DocumentSet) -> tuple[Diagnostic, ...]:
    """Report changed production files without a changed matching test.

    Args:
        document_set: Staged or base change selection.

    Returns:
        Test-pairing diagnostics for unmatched production files.
    """
    return adapter_pairing.test_pairing_diagnostics(document_set, _hooks_module)


def terminology_diagnostics(document_set: DocumentSet) -> tuple[Diagnostic, ...]:
    """Report staged prose that near-misses a newly introduced identifier.

    Args:
        document_set: Candidate staged documents and repository root.

    Returns:
        Diagnostics that name the prose file and line.
    """
    return adapter_detectors.terminology_diagnostics(
        document_set, _pr_loop_script_module
    )


def hook_format_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Check one settings document for a nonportable hook command.

    Args:
        document: Current settings text and path.
        repository_root: Request repository root for document-path resolution.

    Returns:
        A diagnostic when the command uses a home-relative Python script path.
    """
    return adapter_detectors.hook_format_diagnostics(
        document, repository_root, _hooks_module
    )


def accepts_python(document: Document) -> bool:
    return document.path.suffix.lower() == constants.PYTHON_SUFFIX


def accepts_code(document: Document) -> bool:
    """Return whether the document contains supported source code.

    Args:
        document: Candidate document.

    Returns:
        True for a supported source extension.
    """
    return document.path.suffix.lower() in constants.ALL_CODE_SUFFIXES


def accepts_markdown(document: Document) -> bool:
    return document.path.suffix.lower() in constants.ALL_MARKDOWN_SUFFIXES


def accepts_source_or_markdown(document: Document) -> bool:
    """Return whether a state-description rule can inspect the document.

    Args:
        document: Candidate document.

    Returns:
        True for supported source or Markdown.
    """
    return accepts_code(document) or accepts_markdown(document)


def accepts_stored_prompt(document: Document) -> bool:
    """Return whether the document is stored prompt prose.

    Args:
        document: Candidate document.

    Returns:
        True for Markdown in an instruction directory.
    """
    normalized_path = f"/{document.path.as_posix().lower()}"
    return accepts_markdown(document) and any(
        each_segment in normalized_path
        for each_segment in constants.ALL_STORED_PROMPT_SEGMENTS
    )


def accepts_hook_configuration(document: Document) -> bool:
    return document.path.name == "hooks.json"


def accepts_hook_format(document: Document) -> bool:
    """Return whether the document is Claude settings JSON.

    Args:
        document: Candidate document.

    Returns:
        True for ``settings.json`` under a ``.claude`` directory.
    """
    settings_file_name = "settings.json"
    claude_directory_segment = "/.claude/"
    normalized_path = f"/{document.path.as_posix().lower()}"
    return (
        document.path.name.lower() == settings_file_name
        and claude_directory_segment in normalized_path
    )


def accepts_workflow(document: Document) -> bool:
    """Return whether the document is a workflow substitution template.

    Args:
        document: Candidate document.

    Returns:
        True for a ``.workflow.js`` path.
    """
    workflow_constants = _hooks_module(
        "hooks_constants.workflow_substitution_slot_blocker_constants"
    )
    return document.path.as_posix().lower().endswith(
        workflow_constants.WORKFLOW_FILE_SUFFIX
    )


def accepts_plans(document: Document) -> bool:
    """Return whether the document lives in a plan directory.

    Args:
        document: Candidate document.

    Returns:
        True for repository ``docs/plans`` or ``.claude/plans`` paths.
    """
    plans_constants = _hooks_module(
        "hooks_constants.open_questions_in_plans_blocker_constants"
    )
    normalized_path = f"/{document.path.as_posix().lower()}"
    relative_path = document.path.as_posix().lower()
    return (
        plans_constants.PLANS_PATH_SEGMENT in normalized_path
        or plans_constants.DOCS_PLANS_PATH_SEGMENT in normalized_path
        or relative_path.startswith(
            (
                plans_constants.PLANS_PATH_PREFIX,
                plans_constants.DOCS_PLANS_PATH_PREFIX,
            )
        )
    )
