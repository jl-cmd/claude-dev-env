"""Test pairing behavior for changed source documents."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from policy_lint import adapters
from policy_lint.config.approved_test_pairs import (
    APPROVED_TEST_PATHS_BY_PRODUCTION_PATH,
)
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


def test_approved_pairs_name_files_that_exist() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    for (
        production_path,
        all_test_paths,
    ) in APPROVED_TEST_PATHS_BY_PRODUCTION_PATH.items():
        assert (repository_root / production_path).is_file(), production_path
        for each_test_path in all_test_paths:
            assert (repository_root / each_test_path).is_file(), each_test_path


def test_every_approved_pair_actually_waives_its_production_file(tmp_path: Path) -> None:
    """Each mapping entry must silence the rule when its production file changes.

    File existence alone leaves an entry inert when its key carries a suffix the
    rule skips, or when its value is not a name the rule reads as a test.
    """
    for (
        production_path,
        all_test_paths,
    ) in APPROVED_TEST_PATHS_BY_PRODUCTION_PATH.items():
        production_document = Document(
            production_path,
            _BODY_AFTER,
            _BODY_BEFORE,
            frozenset({1}),
            ContentOrigin.REVISION_DIFF,
        )
        for each_test_path in all_test_paths:
            test_document = Document(
                each_test_path,
                _BODY_AFTER,
                _BODY_BEFORE,
                frozenset({1}),
                ContentOrigin.REVISION_DIFF,
            )
            document_set = DocumentSet(
                (production_document, test_document), SelectionKind.BASE, tmp_path
            )
            assert adapters.test_pairing_diagnostics(document_set) == (), production_path


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


_MECHANICAL_BEFORE = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(command, timeout=TIMEOUT_SECONDS, check=False)
        return completed.returncode
    return 1
'''
_KEYWORD_ADDED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, creationflags=0
        )
        return completed.returncode
    return 1
'''
_IMPORT_AND_KEYWORD_ADDED = '''"""Before."""

import os
import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, creationflags=os.O_RDONLY
        )
        return completed.returncode
    return 1
'''
_DOCSTRING_AND_KEYWORD_CHANGED = '''"""After."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command and report its exit status."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, creationflags=0
        )
        return completed.returncode
    return 1
'''
_KEYWORD_ADDED_AND_LITERAL_CHANGED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 6


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, creationflags=0
        )
        return completed.returncode
    return 1
'''
_KEYWORD_VALUE_CHANGED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(command, timeout=TIMEOUT_SECONDS, check=True)
        return completed.returncode
    return 1
'''
_KEYWORD_VALUE_TYPE_CHANGED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(command, timeout=TIMEOUT_SECONDS, check=0)
        return completed.returncode
    return 1
'''
_KEYWORD_REMOVED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(command, timeout=TIMEOUT_SECONDS)
        return completed.returncode
    return 1
'''
_POSITIONAL_CHANGED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command[:1], timeout=TIMEOUT_SECONDS, check=False, creationflags=0
        )
        return completed.returncode
    return 1
'''
_STATEMENT_ADDED_IN_BODY = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, creationflags=0
        )
        completed.check_returncode()
        return completed.returncode
    return 1
'''
_CONDITION_CHANGED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 1:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, creationflags=0
        )
        return completed.returncode
    return 1
'''
_IMPORT_REMOVED = '''"""Before."""

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, creationflags=0
        )
        return completed.returncode
    return 1
'''
_UNPARSEABLE = "def work(:\n    return None\n"


def _mechanical_diagnostics(
    temporary_path: Path, current_source: str, suffix: str = ".py"
) -> tuple[Diagnostic, ...]:
    return _pairing_diagnostics(
        temporary_path,
        _changed_document(current_source, _MECHANICAL_BEFORE, suffix),
    )


def test_pairing_waives_one_added_keyword_argument(tmp_path: Path) -> None:
    assert _mechanical_diagnostics(tmp_path, _KEYWORD_ADDED) == ()


def test_pairing_waives_an_added_import_beside_an_added_keyword(
    tmp_path: Path,
) -> None:
    assert _mechanical_diagnostics(tmp_path, _IMPORT_AND_KEYWORD_ADDED) == ()


def test_pairing_waives_a_docstring_edit_beside_an_added_keyword(
    tmp_path: Path,
) -> None:
    assert _mechanical_diagnostics(tmp_path, _DOCSTRING_AND_KEYWORD_CHANGED) == ()


def test_pairing_reports_an_added_keyword_beside_a_changed_literal(
    tmp_path: Path,
) -> None:
    assert (
        len(_mechanical_diagnostics(tmp_path, _KEYWORD_ADDED_AND_LITERAL_CHANGED)) == 1
    )


def test_pairing_reports_a_changed_keyword_value(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _KEYWORD_VALUE_CHANGED)) == 1


def test_pairing_reports_a_keyword_value_that_changed_literal_type(
    tmp_path: Path,
) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _KEYWORD_VALUE_TYPE_CHANGED)) == 1


def test_pairing_reports_a_removed_keyword(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _KEYWORD_REMOVED)) == 1


def test_pairing_reports_a_changed_positional_argument(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _POSITIONAL_CHANGED)) == 1


def test_pairing_reports_a_statement_added_inside_a_function(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _STATEMENT_ADDED_IN_BODY)) == 1


def test_pairing_reports_a_changed_if_condition(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _CONDITION_CHANGED)) == 1


def test_pairing_reports_a_removed_import(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _IMPORT_REMOVED)) == 1


def test_pairing_reports_a_non_python_document_with_the_same_shape(
    tmp_path: Path,
) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _KEYWORD_ADDED, ".ts")) == 1


def test_pairing_reports_unparseable_current_source(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _UNPARSEABLE)) == 1


def test_pairing_reports_unparseable_prior_source(tmp_path: Path) -> None:
    all_diagnostics = _pairing_diagnostics(
        tmp_path, _changed_document(_KEYWORD_ADDED, _UNPARSEABLE)
    )
    assert len(all_diagnostics) == 1


def test_pairing_reports_an_added_document_without_prior_text(tmp_path: Path) -> None:
    added_document = Document(
        PurePosixPath("src/feature.py"),
        _KEYWORD_ADDED,
        None,
        frozenset({1}),
        ContentOrigin.REVISION_DIFF,
    )
    assert len(_pairing_diagnostics(tmp_path, added_document)) == 1


_MAPPING_UNPACKING_ADDED = '''"""Before."""

import subprocess

TIMEOUT_SECONDS = 5


def work(command: list[str]) -> int:
    """Run one command."""
    if TIMEOUT_SECONDS > 0:
        completed = subprocess.run(
            command, timeout=TIMEOUT_SECONDS, check=False, **{"creationflags": 0}
        )
        return completed.returncode
    return 1
'''


def test_pairing_reports_added_mapping_unpacking_on_a_call(tmp_path: Path) -> None:
    assert len(_mechanical_diagnostics(tmp_path, _MAPPING_UNPACKING_ADDED)) == 1
_INSTALLER_PRODUCTION_PATHS = (
    PurePosixPath("packages/claude-dev-env/bin/install-constants.mjs"),
    PurePosixPath("packages/claude-dev-env/bin/install.mjs"),
)
_INSTALLER_SUITE_PATH = PurePosixPath(
    "packages/claude-dev-env/bin/install.cursor-rules.test.mjs"
)


def test_pairing_accepts_installer_modules_with_the_cursor_rules_suite(
    tmp_path: Path,
) -> None:
    all_paths = _diagnostic_paths(
        tmp_path,
        *(_body_change_at(each_path) for each_path in _INSTALLER_PRODUCTION_PATHS),
        _body_change_at(_INSTALLER_SUITE_PATH),
    )
    assert all_paths == ()


_COMMENT_RULES_PRODUCTION_PATH = PurePosixPath(
    "packages/claude-dev-env/hooks/blocking/code_rules_comments.py"
)
_COMMENT_RULES_SUITE_PATH = PurePosixPath(
    "packages/claude-dev-env/hooks/blocking/test_code_rules_enforcer_comment_string_awareness.py"
)


def test_pairing_accepts_comment_rules_module_with_one_approved_suite(
    tmp_path: Path,
) -> None:
    all_paths = _diagnostic_paths(
        tmp_path,
        _body_change_at(_COMMENT_RULES_PRODUCTION_PATH),
        _body_change_at(_COMMENT_RULES_SUITE_PATH),
    )
    assert all_paths == ()


def test_pairing_rejects_comment_rules_module_without_any_approved_suite(
    tmp_path: Path,
) -> None:
    all_paths = _diagnostic_paths(tmp_path, _body_change_at(_COMMENT_RULES_PRODUCTION_PATH))
    assert all_paths == (_COMMENT_RULES_PRODUCTION_PATH,)
