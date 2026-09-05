"""Archive boundaries for automatic and explicitly requested policy checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest
from policy_lint.engine import _runtime_document_set, lint
from policy_lint.model import (
    Diagnostic,
    Document,
    DocumentRule,
    DocumentSet,
    LintRequest,
    Location,
    SelectionKind,
    Severity,
    TextDocument,
)


def _git(repository_root: Path, *arguments: str) -> None:
    environment = {
        variable_name: variable_text
        for variable_name, variable_text in os.environ.items()
        if not variable_name.upper().startswith("GIT_")
    }
    subprocess.run(
        ["git", *arguments], cwd=repository_root, env=environment,
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def archive_repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--quiet", "-b", "main")
    _git(tmp_path, "config", "user.name", "Archive Tests")
    _git(tmp_path, "config", "user.email", "archive@example.invalid")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    for relative_path in ("active.py", "skill-archive/old.py", "src/skill-archive/live.py"):
        file_path = tmp_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("first\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "--quiet", "-m", "archive fixture")
    for file_path in tmp_path.rglob("*.py"):
        file_path.write_text("second\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    return tmp_path


def _marker_diagnostics(document: Document, repository_root: Path) -> tuple[Diagnostic, ...]:
    assert (repository_root / document.path).is_file()
    return (Diagnostic("marker", Severity.ERROR, "Checked document", Location(document.path, 1)),)


def _accept_document(document: Document) -> bool:
    return bool(document.path.parts)


def _marker_rule() -> DocumentRule:
    return DocumentRule(
        "marker", frozenset({"changed", "repository"}),
        _accept_document, _marker_diagnostics,
    )


@pytest.mark.parametrize("selection", (SelectionKind.STAGED, SelectionKind.BASE, SelectionKind.REPOSITORY))
def test_automatic_checks_keep_live_code_and_exclude_only_root_archive(
    archive_repository: Path, selection: SelectionKind,
) -> None:
    requests = {
        SelectionKind.STAGED: LintRequest.staged(archive_repository),
        SelectionKind.BASE: LintRequest.base(archive_repository, "HEAD"),
        SelectionKind.REPOSITORY: LintRequest.repository(archive_repository),
    }
    report = lint(requests[selection], all_registry=(_marker_rule(),))
    assert report.checked_documents == (
        PurePosixPath("active.py"), PurePosixPath("src/skill-archive/live.py"),
    )
    assert len(report.diagnostics) == 2
    assert report.executed_rules == ("marker",)
    assert report.exit_code == 1


@pytest.mark.parametrize("selection", (SelectionKind.FILES, SelectionKind.TEXT))
def test_explicit_archive_checks_still_execute_rules(
    archive_repository: Path, selection: SelectionKind,
) -> None:
    archive_path = Path("skill-archive/old.py")
    request = (
        LintRequest.files(archive_repository, [archive_path])
        if selection is SelectionKind.FILES
        else LintRequest(archive_repository, TextDocument(archive_path, "editor text\n"))
    )
    report = lint(request, all_registry=(_marker_rule(),))
    assert report.checked_documents == (PurePosixPath("skill-archive/old.py"),)
    assert len(report.diagnostics) == 1
    assert report.exit_code == 1


def test_retirement_and_restoration_preserve_live_change_metadata(tmp_path: Path) -> None:
    retired_path = PurePosixPath("active/retired.py")
    archive_path = PurePosixPath("skill-archive/retired.py")
    restored_source = PurePosixPath("skill-archive/restored.py")
    restored_path = PurePosixPath("active/restored.py")
    deleted_path = PurePosixPath("active/deleted.py")
    document_set = DocumentSet(
        (Document.from_text(archive_path, "archived"), Document.from_text(restored_path, "restored")),
        SelectionKind.BASE,
        tmp_path,
        (deleted_path, PurePosixPath("skill-archive/deleted.py")),
        ((retired_path, archive_path), (restored_source, restored_path)),
        base_revision="base-sha",
    )
    runtime_set = _runtime_document_set(document_set)
    assert tuple(document.path for document in runtime_set.documents) == (restored_path,)
    assert runtime_set.deleted_paths == (deleted_path, retired_path)
    assert runtime_set.renamed_paths == ((restored_source, restored_path),)
    assert runtime_set.base_revision == "base-sha"
