"""Test pairing behavior for changed source documents."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from policy_lint import adapters
from policy_lint.model import (
    ContentOrigin,
    Diagnostic,
    Document,
    DocumentSet,
    SelectionKind,
)

_MODULE_DOCSTRING_BEFORE = '''"""Before."""

def work() -> None:
    """Old function documentation."""
    return None
'''
_MODULE_DOCSTRING_AFTER = '''"""After."""

def work() -> None:
    """Updated function documentation."""
    return None
'''
_BODY_BEFORE = '''"""Before."""

def work() -> None:
    return None
'''
_BODY_AFTER = '''"""After."""

def work() -> None:
    return 1
'''


def _changed_document(
    current_source: str, prior_source: str, suffix: str = ".py"
) -> Document:
    return Document(
        PurePosixPath(f"src/feature{suffix}"),
        current_source,
        prior_source,
        frozenset({1}),
        ContentOrigin.REVISION_DIFF,
    )


def _pairing_diagnostics(
    temporary_path: Path, changed_document: Document
) -> tuple[Diagnostic, ...]:
    document_set = DocumentSet((changed_document,), SelectionKind.BASE, temporary_path)
    return adapters.test_pairing_diagnostics(document_set)


def test_pairing_ignores_python_docstring_only_changes(tmp_path: Path) -> None:
    all_diagnostics = _pairing_diagnostics(
        tmp_path,
        _changed_document(_MODULE_DOCSTRING_AFTER, _MODULE_DOCSTRING_BEFORE),
    )
    assert all_diagnostics == ()


def test_pairing_requires_a_test_for_python_body_changes(tmp_path: Path) -> None:
    all_diagnostics = _pairing_diagnostics(
        tmp_path,
        _changed_document(_BODY_AFTER, _BODY_BEFORE),
    )
    assert len(all_diagnostics) == 1


def test_pairing_rejects_python_syntax_errors_without_a_test(tmp_path: Path) -> None:
    all_diagnostics = _pairing_diagnostics(
        tmp_path,
        _changed_document("def work(:\n    return None\n", _BODY_BEFORE),
    )
    assert len(all_diagnostics) == 1


def test_pairing_keeps_non_python_changes_on_existing_matching_rules(
    tmp_path: Path,
) -> None:
    all_diagnostics = _pairing_diagnostics(
        tmp_path,
        _changed_document(
            "export const work = 1;\n", "export const work = 2;\n", ".ts"
        ),
    )
    assert len(all_diagnostics) == 1


_APPROVED_PRODUCTION_PATH = PurePosixPath(
    "packages/claude-dev-env/scripts/automatic_advisory/state.py"
)
_APPROVED_TEST_PATH = PurePosixPath(
    "packages/claude-dev-env/scripts/tests/test_closed_pr_label.py"
)
_UNRELATED_PRODUCTION_PATH = PurePosixPath(
    "packages/claude-dev-env/scripts/automatic_advisory/new_module.py"
)


def _body_change_at(path: PurePosixPath) -> Document:
    return Document(
        path, _BODY_AFTER, _BODY_BEFORE, frozenset({4}), ContentOrigin.REVISION_DIFF
    )


def _diagnostic_paths(
    temporary_path: Path, *all_documents: Document
) -> tuple[PurePosixPath, ...]:
    document_set = DocumentSet(all_documents, SelectionKind.BASE, temporary_path)
    return tuple(
        each_diagnostic.location.path
        for each_diagnostic in adapters.test_pairing_diagnostics(document_set)
    )


def test_pairing_accepts_an_approved_module_with_its_changed_suite(
    tmp_path: Path,
) -> None:
    all_paths = _diagnostic_paths(
        tmp_path,
        _body_change_at(_APPROVED_PRODUCTION_PATH),
        _body_change_at(_APPROVED_TEST_PATH),
    )
    assert all_paths == ()


def test_pairing_rejects_an_approved_module_without_its_suite(
    tmp_path: Path,
) -> None:
    all_paths = _diagnostic_paths(tmp_path, _body_change_at(_APPROVED_PRODUCTION_PATH))
    assert all_paths == (_APPROVED_PRODUCTION_PATH,)


def test_pairing_rejects_an_unrelated_module_beside_a_changed_approved_suite(
    tmp_path: Path,
) -> None:
    all_paths = _diagnostic_paths(
        tmp_path,
        _body_change_at(_APPROVED_PRODUCTION_PATH),
        _body_change_at(_UNRELATED_PRODUCTION_PATH),
        _body_change_at(_APPROVED_TEST_PATH),
    )
    assert all_paths == (_UNRELATED_PRODUCTION_PATH,)
