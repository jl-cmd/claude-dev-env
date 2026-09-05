"""Document-selection boundary tests for files, staged, base, and repository sources."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest
from policy_lint import selection as selection_module
from policy_lint import selection_git
from policy_lint.config import constants
from policy_lint.model import (
    ContentOrigin,
    Document,
    DocumentSet,
    LintRequest,
    SelectionKind,
)
from policy_lint.selection import SelectionRunFatal, select_documents


def _git_environment() -> dict[str, str]:
    return {
        each_name: each_environment_text
        for each_name, each_environment_text in os.environ.items()
        if not each_name.upper().startswith("GIT_")
    }


def _git_stdout(repository_root: Path, *all_arguments: str) -> str:
    completed = subprocess.run(
        [constants.GIT_EXECUTABLE, *all_arguments],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        env=_git_environment(),
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _run_git(repository_root: Path, *all_arguments: str) -> None:
    _git_stdout(repository_root, *all_arguments)


def _initialize_repository(repository_root: Path) -> Path:
    _run_git(repository_root, "init", "--quiet", "-b", "main")
    _run_git(repository_root, "config", "user.name", "Selection Tests")
    _run_git(repository_root, "config", "user.email", "selection@example.invalid")
    _run_git(repository_root, "config", "commit.gpgsign", "false")
    _run_git(repository_root, "config", "core.autocrlf", "false")
    return repository_root


def _write_text(repository_root: Path, relative_path: str, text: str) -> None:
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(text.encode(constants.UTF8_ENCODING))


def _commit_text(repository_root: Path, relative_path: str, text: str) -> None:
    _write_text(repository_root, relative_path, text)
    _run_git(repository_root, "add", "--", relative_path)
    _run_git(repository_root, "commit", "--quiet", "-m", "selection fixture")


def _document_for(document_set: DocumentSet, relative_path: str) -> Document:
    for each_document in document_set.documents:
        if each_document.path.as_posix() == relative_path:
            return each_document
    raise AssertionError(f"missing document: {relative_path}")


def test_files_source_should_read_current_worktree_bytes(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "file.py", "committed\n")
    _write_text(repository_root, "file.py", "worktree\n")

    document_set = select_documents(
        LintRequest.files(repository_root, [Path("file.py")])
    )
    selected_document = _document_for(document_set, "file.py")

    assert document_set.selection == SelectionKind.FILES
    assert selected_document.text == "worktree\n"
    assert selected_document.origin == ContentOrigin.WORKTREE
    assert selected_document.prior_text is None


def test_staged_modified_file_should_read_index_bytes_not_worktree(
    tmp_path: Path,
) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "file.py", "committed\n")
    _write_text(repository_root, "file.py", "staged\n")
    _run_git(repository_root, "add", "--", "file.py")
    _write_text(repository_root, "file.py", "worktree\n")

    document_set = select_documents(LintRequest.staged(repository_root))
    selected_document = _document_for(document_set, "file.py")

    assert document_set.selection == SelectionKind.STAGED
    assert selected_document.text == "staged\n"
    assert selected_document.prior_text == "committed\n"
    assert selected_document.origin == ContentOrigin.INDEX
    assert selected_document.prior_path is None
    assert document_set.deleted_paths == ()
    assert 1 in (selected_document.changed_lines or frozenset())


def test_staged_added_file_should_have_no_prior_text(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "keep.py", "keep\n")
    _write_text(repository_root, "new.py", "added\n")
    _run_git(repository_root, "add", "--", "new.py")

    document_set = select_documents(LintRequest.staged(repository_root))
    selected_document = _document_for(document_set, "new.py")

    assert selected_document.text == "added\n"
    assert selected_document.prior_text is None
    assert document_set.deleted_paths == ()
    assert selected_document.changed_lines == frozenset({1})


def test_staged_deleted_file_should_record_a_true_delete_only(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "gone.py", "body\n")
    _run_git(repository_root, "rm", "--quiet", "--", "gone.py")

    document_set = select_documents(LintRequest.staged(repository_root))

    assert document_set.documents == ()
    assert document_set.deleted_paths == (PurePosixPath("gone.py"),)
    assert document_set.renamed_paths == ()


def test_staged_renamed_file_should_keep_prior_path_metadata(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "old.py", "body\n")
    _run_git(repository_root, "mv", "--", "old.py", "new.py")

    document_set = select_documents(LintRequest.staged(repository_root))
    selected_document = _document_for(document_set, "new.py")

    assert selected_document.text == "body\n"
    assert selected_document.prior_text == "body\n"
    assert selected_document.prior_path == PurePosixPath("old.py")
    assert document_set.renamed_paths == (
        (PurePosixPath("old.py"), PurePosixPath("new.py")),
    )
    assert document_set.deleted_paths == ()


def test_staged_copied_file_should_not_record_a_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "source.py", "copied-body\n")
    _write_text(repository_root, "copy.py", "copied-body\n")
    _run_git(repository_root, "add", "--", "copy.py")
    original_git_bytes_for = selection_module.git_bytes_for

    def git_bytes_for_with_copy(
        git_repository_root: Path, all_arguments: tuple[str, ...]
    ) -> bytes:
        if constants.GIT_NAME_STATUS_FLAG in all_arguments:
            return b"C100\0source.py\0copy.py\0"
        return original_git_bytes_for(git_repository_root, all_arguments)

    monkeypatch.setattr(selection_module, "git_bytes_for", git_bytes_for_with_copy)
    document_set = select_documents(LintRequest.staged(repository_root))
    selected_document = _document_for(document_set, "copy.py")

    assert selected_document.text == "copied-body\n"
    assert selected_document.prior_path is None
    assert selected_document.prior_text is None
    assert document_set.renamed_paths == ()
    assert document_set.deleted_paths == ()


def test_staged_missing_non_delete_blob_should_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "file.py", "committed\n")
    _write_text(repository_root, "file.py", "staged\n")
    _run_git(repository_root, "add", "--", "file.py")
    original_read_blob = selection_module.read_blob

    def missing_index_blob(
        git_repository_root: Path, revision: str, relative_path: str
    ) -> str | None:
        if revision == constants.GIT_INDEX_REFERENCE_PREFIX:
            return None
        return original_read_blob(git_repository_root, revision, relative_path)

    monkeypatch.setattr(selection_module, "read_blob", missing_index_blob)
    with pytest.raises(SelectionRunFatal, match="unavailable"):
        select_documents(LintRequest.staged(repository_root))


def test_git_blob_unexpected_failure_should_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed_git(
        *_all_arguments: object, **_all_keywords: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[constants.GIT_EXECUTABLE],
            returncode=1,
            stdout=b"",
            stderr=b"fatal: Not a valid object name HEAD:file.py",
        )

    monkeypatch.setattr(selection_git.subprocess, "run", failed_git)
    with pytest.raises(selection_git.GitSelectionError, match="Not a valid object"):
        selection_git.read_blob(tmp_path, "HEAD", "file.py")


def test_unborn_repository_head_should_return_none(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    assert selection_git.head_revision(repository_root) is None


def test_unexpected_head_failure_should_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed_git(
        *_all_arguments: object, **_all_keywords: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=[constants.GIT_EXECUTABLE],
            returncode=1,
            stdout=b"",
            stderr=b"fatal: broken HEAD state",
        )

    monkeypatch.setattr(selection_git.subprocess, "run", failed_git)
    with pytest.raises(selection_git.GitSelectionError, match="broken HEAD"):
        selection_git.head_revision(tmp_path)


def test_base_source_should_compare_merge_base_and_read_worktree_bytes(
    tmp_path: Path,
) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "file.py", "base-text\n")
    _run_git(repository_root, "checkout", "--quiet", "-b", "feature")
    _commit_text(repository_root, "file.py", "feature-committed\n")
    _write_text(repository_root, "file.py", "feature-worktree\n")

    document_set = select_documents(LintRequest.base(repository_root, "main"))
    selected_document = _document_for(document_set, "file.py")

    assert document_set.selection == SelectionKind.BASE
    assert selected_document.text == "feature-worktree\n"
    assert selected_document.prior_text == "base-text\n"
    assert selected_document.origin == ContentOrigin.REVISION_DIFF


def test_base_selection_records_merge_base_revision_and_staged_does_not(
    tmp_path: Path,
) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "file.py", "base-text\n")
    _run_git(repository_root, "checkout", "--quiet", "-b", "feature")
    _commit_text(repository_root, "file.py", "feature-committed\n")

    merge_base = _git_stdout(repository_root, "merge-base", "main", "HEAD")
    base_document_set = select_documents(LintRequest.base(repository_root, "main"))
    staged_document_set = select_documents(LintRequest.staged(repository_root))

    assert base_document_set.base_revision == merge_base
    assert staged_document_set.base_revision is None


def test_repository_source_should_read_tracked_worktree_files_only(
    tmp_path: Path,
) -> None:
    repository_root = _initialize_repository(tmp_path)
    _commit_text(repository_root, "tracked.py", "tracked\n")
    _write_text(repository_root, "untracked.py", "nope\n")

    document_set = select_documents(LintRequest.repository(repository_root))
    all_paths = {
        each_document.path.as_posix() for each_document in document_set.documents
    }
    selected_document = _document_for(document_set, "tracked.py")

    assert document_set.selection == SelectionKind.REPOSITORY
    assert all_paths == {"tracked.py"}
    assert selected_document.text == "tracked\n"
    assert selected_document.origin == ContentOrigin.WORKTREE


def test_prebuilt_document_set_should_keep_repository_relative_paths(
    tmp_path: Path,
) -> None:
    repository_root = _initialize_repository(tmp_path)
    document_set = DocumentSet(
        (
            Document(
                PurePosixPath("ok.py"),
                "text\n",
                None,
                None,
                ContentOrigin.EDITOR,
            ),
        ),
        SelectionKind.TEXT,
        repository_root,
    )

    selected_document_set = select_documents(LintRequest(repository_root, document_set))

    assert selected_document_set.documents[0].path == PurePosixPath("ok.py")
    assert selected_document_set.selection == SelectionKind.TEXT


def test_files_path_outside_repository_should_raise(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    outside_path = repository_root.parent / "escape.py"
    with pytest.raises(SelectionRunFatal, match="outside"):
        select_documents(LintRequest.files(repository_root, [outside_path]))


def test_missing_git_should_raise_a_selection_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_git(_repository_root: Path, _all_arguments: tuple[str, ...]) -> bytes:
        raise FileNotFoundError("git")

    monkeypatch.setattr(selection_module, "git_bytes_for", missing_git)
    with pytest.raises(SelectionRunFatal, match="git"):
        select_documents(LintRequest.files(tmp_path, [Path("file.py")]))


def test_prebuilt_prior_path_outside_repository_should_raise(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    document_set = DocumentSet(
        (
            Document(
                PurePosixPath("ok.py"),
                "text\n",
                None,
                None,
                ContentOrigin.EDITOR,
                PurePosixPath("../escape"),
            ),
        ),
        SelectionKind.TEXT,
        repository_root,
    )
    with pytest.raises(SelectionRunFatal, match="outside"):
        select_documents(LintRequest(repository_root, document_set))


def test_prebuilt_deleted_path_outside_repository_should_raise(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    document_set = DocumentSet(
        (),
        SelectionKind.STAGED,
        repository_root,
        deleted_paths=(PurePosixPath("../escape"),),
    )
    with pytest.raises(SelectionRunFatal, match="outside"):
        select_documents(LintRequest(repository_root, document_set))


def test_prebuilt_renamed_path_outside_repository_should_raise(tmp_path: Path) -> None:
    repository_root = _initialize_repository(tmp_path)
    document_set = DocumentSet(
        (),
        SelectionKind.STAGED,
        repository_root,
        renamed_paths=((PurePosixPath("../escape"), PurePosixPath("ok.py")),),
    )
    with pytest.raises(SelectionRunFatal, match="outside"):
        select_documents(LintRequest(repository_root, document_set))


def test_tracked_worktree_document_preserves_git_path_spelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        selection_module,
        "_read_worktree_text",
        lambda _file_path: "body\n",
    )
    selected_document = selection_module._tracked_worktree_document(
        tmp_path, "MiXeD.py"
    )
    assert selected_document.path == PurePosixPath("MiXeD.py")
