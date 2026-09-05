from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import TypeAlias

from .config.constants import INCOMPLETE_EXIT_CODE


class SelectionKind(StrEnum):
    FILES = "files"
    STAGED = "staged"
    BASE = "base"
    REPOSITORY = "repository"
    TEXT = "text"


class ContentOrigin(StrEnum):
    WORKTREE = "worktree"
    INDEX = "index"
    REVISION_DIFF = "revision_diff"
    TRACKED_TREE = "tracked_tree"
    EDITOR = "editor"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class RuleScope(StrEnum):
    DOCUMENT = "document"
    CHANGESET = "changeset"
    REPOSITORY = "repository"


@dataclass(frozen=True)
class ExplicitFiles:
    paths: tuple[Path, ...]


@dataclass(frozen=True)
class StagedChanges:
    pass


@dataclass(frozen=True)
class BaseChanges:
    revision: str


@dataclass(frozen=True)
class RepositoryTree:
    pass


@dataclass(frozen=True)
class TextDocument:
    path: Path
    text: str


LintSource: TypeAlias = (
    ExplicitFiles | StagedChanges | BaseChanges | RepositoryTree | TextDocument
)


@dataclass(frozen=True)
class Document:
    path: PurePosixPath
    text: str
    prior_text: str | None
    changed_lines: frozenset[int] | None
    origin: ContentOrigin
    prior_path: PurePosixPath | None = None

    @classmethod
    def from_text(
        cls,
        path: str | PurePosixPath,
        text: str,
        origin: ContentOrigin = ContentOrigin.EDITOR,
    ) -> Document:
        """Build a document from an unsaved text buffer.

        Args:
            path: Repository-relative document path.
            text: Unsaved document text.
            origin: Content source label.

        Returns:
            A document with no prior content.
        """
        normalized_path = PurePosixPath(
            path.as_posix() if isinstance(path, PurePosixPath) else path
        )
        return cls(normalized_path, text, None, None, origin)


@dataclass(frozen=True)
class DocumentSet:
    documents: tuple[Document, ...]
    selection: SelectionKind
    repository_root: Path
    deleted_paths: tuple[PurePosixPath, ...] = ()
    renamed_paths: tuple[tuple[PurePosixPath, PurePosixPath], ...] = ()
    base_revision: str | None = None


@dataclass(frozen=True)
class LintRequest:
    repository_root: Path
    source: LintSource | DocumentSet
    rule_sets: frozenset[str] = frozenset({"changed"})

    @classmethod
    def files(
        cls,
        repository_root: Path,
        all_paths: Sequence[Path],
        all_rule_sets: frozenset[str] = frozenset({"changed"}),
    ) -> LintRequest:
        """Build a request for current worktree files.

        Args:
            repository_root: Repository root.
            all_paths: Files to read.
            all_rule_sets: Rule sets requested by the caller.

        Returns:
            A file-selection request.
        """
        return cls(repository_root, ExplicitFiles(tuple(all_paths)), all_rule_sets)

    @classmethod
    def staged(
        cls,
        repository_root: Path,
        all_rule_sets: frozenset[str] = frozenset({"changed"}),
    ) -> LintRequest:
        """Build a request for staged index content.

        Args:
            repository_root: Repository root.
            all_rule_sets: Rule sets requested by the caller.

        Returns:
            A staged-selection request.
        """
        return cls(repository_root, StagedChanges(), all_rule_sets)

    @classmethod
    def base(
        cls,
        repository_root: Path,
        revision: str,
        all_rule_sets: frozenset[str] = frozenset({"changed"}),
    ) -> LintRequest:
        """Build a request for changes against a base revision.

        Args:
            repository_root: Repository root.
            revision: Revision that identifies the merge-base comparison.
            all_rule_sets: Rule sets requested by the caller.

        Returns:
            A base-selection request.
        """
        return cls(repository_root, BaseChanges(revision), all_rule_sets)

    @classmethod
    def repository(
        cls,
        repository_root: Path,
        all_rule_sets: frozenset[str] = frozenset({"repository"}),
    ) -> LintRequest:
        """Build a request for tracked worktree files.

        Args:
            repository_root: Repository root.
            all_rule_sets: Rule sets requested by the caller.

        Returns:
            A repository-selection request.
        """
        return cls(repository_root, RepositoryTree(), all_rule_sets)

    @classmethod
    def documents(
        cls,
        repository_root: Path,
        all_documents: Sequence[Document],
        all_rule_sets: frozenset[str] = frozenset({"changed"}),
    ) -> LintRequest:
        """Build a request from already selected documents.

        Args:
            repository_root: Repository root.
            all_documents: Documents available to rules.
            all_rule_sets: Rule sets requested by the caller.

        Returns:
            A document-set request.
        """
        document_set = DocumentSet(
            tuple(all_documents), SelectionKind.TEXT, repository_root
        )
        return cls(repository_root, document_set, all_rule_sets)


@dataclass(frozen=True)
class Location:
    path: PurePosixPath
    start_line: int
    start_column: int = 1
    end_line: int | None = None
    end_column: int | None = None

    def normalized(self) -> Location:
        """Fill omitted range endpoints with the start position.

        Returns:
            A location with complete source-range endpoints.
        """
        return Location(
            self.path,
            self.start_line,
            self.start_column,
            self.end_line if self.end_line is not None else self.start_line,
            self.end_column if self.end_column is not None else self.start_column,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible source location.

        Returns:
            The normalized location mapping.
        """
        normalized_location = self.normalized()
        return {
            "path": normalized_location.path.as_posix(),
            "start_line": normalized_location.start_line,
            "start_column": normalized_location.start_column,
            "end_line": normalized_location.end_line,
            "end_column": normalized_location.end_column,
        }


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    severity: Severity
    message: str
    location: Location | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible diagnostic.

        Returns:
            The diagnostic mapping.
        """
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "location": None if self.location is None else self.location.as_dict(),
        }


DocumentChecker: TypeAlias = Callable[[Document, Path], Iterable[Diagnostic]]
DocumentSetChecker: TypeAlias = Callable[[DocumentSet], Iterable[Diagnostic]]


@dataclass(frozen=True)
class DocumentRule:
    rule_id: str
    rule_sets: frozenset[str]
    accepts: Callable[[Document], bool]
    check: DocumentChecker


@dataclass(frozen=True)
class ChangeSetRule:
    rule_id: str
    rule_sets: frozenset[str]
    selections: frozenset[SelectionKind]
    check: DocumentSetChecker


@dataclass(frozen=True)
class RepositoryRule:
    rule_id: str
    rule_sets: frozenset[str]
    check: DocumentSetChecker


Rule: TypeAlias = DocumentRule | ChangeSetRule | RepositoryRule


@dataclass(frozen=True)
class EditorDiagnostic:
    path: PurePosixPath
    line: int
    column: int
    message: str
    severity: Severity
    rule_id: str

    def as_dict(self) -> dict[str, object]:
        """Return an editor-compatible diagnostic mapping.

        Returns:
            The editor diagnostic mapping.
        """
        return {
            "path": self.path.as_posix(),
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity.value,
            "rule_id": self.rule_id,
        }


@dataclass(frozen=True)
class LintReport:
    schema_version: int
    diagnostics: tuple[Diagnostic, ...]
    checked_documents: tuple[PurePosixPath, ...]
    executed_rules: tuple[str, ...]
    failed_rules: tuple[str, ...]
    skipped_rules: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        """Return the process exit code for this report.

        Returns:
            Zero for clean output, one for findings, or three for rule failure.
        """
        if self.failed_rules:
            return INCOMPLETE_EXIT_CODE
        if self.diagnostics:
            return 1
        return 0

    def as_dict(self) -> dict[str, object]:
        """Return the JSON result.

        Returns:
            The complete report mapping.
        """
        return {
            "schema_version": self.schema_version,
            "diagnostics": [
                each_diagnostic.as_dict() for each_diagnostic in self.diagnostics
            ],
            "checked_documents": [
                each_path.as_posix() for each_path in self.checked_documents
            ],
            "executed_rules": list(self.executed_rules),
            "failed_rules": list(self.failed_rules),
            "skipped_rules": list(self.skipped_rules),
        }

    def editor_diagnostics(self) -> tuple[EditorDiagnostic, ...]:
        """Return source-located diagnostics in editor wire format.

        Returns:
            Diagnostics that carry a source location.
        """
        all_editor_diagnostics: list[EditorDiagnostic] = []
        for each_diagnostic in self.diagnostics:
            if each_diagnostic.location is None:
                continue
            normalized_location = each_diagnostic.location.normalized()
            all_editor_diagnostics.append(
                EditorDiagnostic(
                    path=normalized_location.path,
                    line=normalized_location.start_line,
                    column=normalized_location.start_column,
                    message=each_diagnostic.message,
                    severity=each_diagnostic.severity,
                    rule_id=each_diagnostic.rule_id,
                )
            )
        return tuple(all_editor_diagnostics)
