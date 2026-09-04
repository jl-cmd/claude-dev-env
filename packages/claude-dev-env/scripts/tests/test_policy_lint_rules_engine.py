"""Engine and diagnostic adapter tests for policy lint."""

from __future__ import annotations

import subprocess
import types
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath

import pytest
from policy_lint import adapters
from policy_lint.config.constants import INCOMPLETE_EXIT_CODE
from policy_lint.engine import lint
from policy_lint.model import (
    ContentOrigin,
    Diagnostic,
    Document,
    DocumentRule,
    DocumentSet,
    LintReport,
    LintRequest,
    Location,
    SelectionKind,
    Severity,
)

_CHANGED_RULE_SETS = frozenset({"changed"})
_SAMPLE_SOURCE = "x = 1\n"


def _accepts_every_document(document: Document) -> bool:
    return document.path.as_posix() != ""


def _source_document(
    relative_path: str,
    changed_lines: frozenset[int] | None = None,
) -> Document:
    return Document(
        PurePosixPath(relative_path),
        _SAMPLE_SOURCE,
        None,
        changed_lines,
        ContentOrigin.EDITOR,
    )


def _changed_document_rule(
    rule_id: str,
    collect_diagnostics: Callable[[Document, Path], Iterable[Diagnostic]],
) -> DocumentRule:
    return DocumentRule(
        rule_id, _CHANGED_RULE_SETS, _accepts_every_document, collect_diagnostics
    )


def _ensure_git_repository(repository_root: Path) -> None:
    git_directory = repository_root / ".git"
    if git_directory.exists():
        return
    subprocess.run(
        ("git", "init"),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def _lint_documents(
    repository_root: Path,
    all_documents: tuple[Document, ...],
    all_rules: tuple[DocumentRule, ...],
) -> LintReport:
    _ensure_git_repository(repository_root)
    document_set = DocumentSet(all_documents, SelectionKind.TEXT, repository_root)
    request = LintRequest(repository_root, document_set)
    return lint(request, all_registry=all_rules)


def _flaky_diagnostics(document: Document) -> tuple[Diagnostic, ...]:
    if document.path.name == "second.py":
        raise ImportError("detector missing")
    return (
        Diagnostic(
            "flaky",
            Severity.ERROR,
            "partial finding",
            Location(document.path, 2, 1),
        ),
    )


def _stable_diagnostics(document: Document) -> tuple[Diagnostic, ...]:
    return (
        Diagnostic(
            "stable",
            Severity.ERROR,
            "kept finding",
            Location(document.path, 3, 1),
        ),
    )


def test_line_prefix_message_keeps_real_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_hooks_module(module_name: str) -> object:
        if not module_name:
            raise AssertionError("missing module")
        return types.SimpleNamespace(
            validate_content_for_full_gate=lambda *args, **kwargs: [
                "Line 47: comment found"
            ]
        )

    monkeypatch.setattr(adapters, "_hooks_module", fake_hooks_module)
    all_diagnostics = adapters.code_rule_diagnostics(
        Document.from_text("pkg/mod.py", _SAMPLE_SOURCE), tmp_path
    )
    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].location is not None
    assert all_diagnostics[0].location.start_line == 47


def test_path_line_message_keeps_real_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_outcome = types.SimpleNamespace(
        name="ruff",
        passed=False,
        output="C:/Users/example/AppData/Local/Temp/tmp123/pkg/mod.py:47: magic number",
    )

    def fake_hooks_module(module_name: str) -> object:
        if not module_name:
            raise AssertionError("missing module")
        return types.SimpleNamespace(
            validate_proposed_file=lambda *args, **kwargs: [fake_outcome]
        )

    monkeypatch.setattr(adapters, "_hooks_module", fake_hooks_module)
    all_diagnostics = adapters.validator_diagnostics(
        Document.from_text("pkg/mod.py", _SAMPLE_SOURCE), tmp_path
    )
    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].location is not None
    assert all_diagnostics[0].location.start_line == 47
    assert all_diagnostics[0].message == "pkg/mod.py:47: magic number"


def test_unknown_line_has_no_location() -> None:
    document = Document.from_text("pkg/mod.py", _SAMPLE_SOURCE)
    all_diagnostics = adapters._diagnostics_for_messages(
        document, "plain-language", ("Banned prose term: landscape",)
    )
    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].location is None


def test_changed_line_filter_keeps_matching_line(tmp_path: Path) -> None:
    repository_root = tmp_path.resolve()
    document = _source_document("pkg/mod.py", changed_lines=frozenset({47}))

    def collect_diagnostics(
        document: Document, repository_root: Path | None = None
    ) -> tuple[Diagnostic, ...]:
        del repository_root
        return (
            Diagnostic(
                "code-rules",
                Severity.ERROR,
                "Line 47: comment found",
                Location(document.path, 47, 1),
            ),
        )

    lint_report = _lint_documents(
        repository_root,
        (document,),
        (_changed_document_rule("code-rules", collect_diagnostics),),
    )
    assert len(lint_report.diagnostics) == 1
    assert lint_report.diagnostics[0].location is not None
    assert lint_report.diagnostics[0].location.start_line == 47


def test_changed_line_filter_drops_other_located_line(tmp_path: Path) -> None:
    repository_root = tmp_path.resolve()
    document = _source_document("pkg/mod.py", changed_lines=frozenset({1}))

    def collect_diagnostics(
        document: Document, repository_root: Path | None = None
    ) -> tuple[Diagnostic, ...]:
        del repository_root
        return (
            Diagnostic(
                "code-rules",
                Severity.ERROR,
                "Line 47: comment found",
                Location(document.path, 47, 1),
            ),
        )

    lint_report = _lint_documents(
        repository_root,
        (document,),
        (_changed_document_rule("code-rules", collect_diagnostics),),
    )
    assert lint_report.diagnostics == ()


def test_lint_keeps_located_findings_when_changed_lines_are_empty(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path.resolve()
    document = _source_document("pkg/mod.py", changed_lines=frozenset())

    def collect_diagnostics(
        document: Document, repository_root: Path | None = None
    ) -> tuple[Diagnostic, ...]:
        del repository_root
        return (
            Diagnostic(
                "probe",
                Severity.ERROR,
                "finding",
                Location(document.path, 1, 1),
            ),
        )

    lint_report = _lint_documents(
        repository_root,
        (document,),
        (_changed_document_rule("probe", collect_diagnostics),),
    )
    assert len(lint_report.diagnostics) == 1


def test_code_rule_diagnostics_includes_comment_policy_without_prior_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    include_comment_policy: dict[str, bool] = {}

    def validate_content_for_full_gate(
        *all_arguments: object, **all_keywords: object
    ) -> list[str]:
        del all_arguments
        include_comment_policy["enabled"] = bool(all_keywords["include_comment_policy"])
        return []

    monkeypatch.setattr(
        adapters,
        "_hooks_module",
        lambda _module_name: types.SimpleNamespace(
            validate_content_for_full_gate=validate_content_for_full_gate
        ),
    )
    adapters.code_rule_diagnostics(
        Document.from_text("pkg/new.py", _SAMPLE_SOURCE), tmp_path
    )
    assert include_comment_policy == {"enabled": True}


def test_code_rule_diagnostics_keeps_legacy_stdout_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def validate_content_for_full_gate(
        *all_arguments: object, **all_keywords: object
    ) -> list[str]:
        del all_arguments, all_keywords
        print("large file advisory")
        return ["Line 2: real diagnostic"]

    monkeypatch.setattr(
        adapters,
        "_hooks_module",
        lambda _module_name: types.SimpleNamespace(
            validate_content_for_full_gate=validate_content_for_full_gate
        ),
    )
    all_diagnostics = adapters.code_rule_diagnostics(
        Document.from_text("pkg/mod.py", _SAMPLE_SOURCE), tmp_path
    )
    captured_output = capsys.readouterr()
    assert captured_output.out == ""
    assert captured_output.err == ""
    assert [each_diagnostic.message for each_diagnostic in all_diagnostics] == [
        "Line 2: real diagnostic"
    ]


def test_state_description_diagnostics_maps_and_scopes_phrases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapters,
        "_hooks_module",
        lambda _module_name: types.SimpleNamespace(
            find_violations=lambda _text, _path: ["used to", "replaced by"]
        ),
    )
    source_document = Document(
        PurePosixPath("module.py"),
        "# " + "replaced" + " by unchanged\n# " + "used" + " to changed\n",
        None,
        frozenset({2}),
        ContentOrigin.EDITOR,
    )
    lint_report = _lint_documents(
        tmp_path,
        (source_document,),
        (_changed_document_rule("state-description", adapters.state_description_diagnostics),),
    )
    assert len(lint_report.diagnostics) == 1
    assert lint_report.diagnostics[0].location is not None
    assert lint_report.diagnostics[0].location.start_line == 2


def test_unlocated_finding_survives_changed_line_filter(tmp_path: Path) -> None:
    repository_root = tmp_path.resolve()
    document = _source_document("pkg/mod.py", changed_lines=frozenset({8}))

    def collect_diagnostics(
        document: Document, repository_root: Path | None = None
    ) -> tuple[Diagnostic, ...]:
        del repository_root
        return (
            Diagnostic(
                "plain-language",
                Severity.ERROR,
                "Banned prose term: landscape",
                None,
            ),
        )

    lint_report = _lint_documents(
        repository_root,
        (document,),
        (_changed_document_rule("plain-language", collect_diagnostics),),
    )
    assert len(lint_report.diagnostics) == 1
    assert lint_report.diagnostics[0].location is None


def test_failed_adapter_rolls_back_continues_and_exits_incomplete(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path.resolve()
    all_documents = (
        _source_document("pkg/first.py"),
        _source_document("pkg/second.py"),
    )
    all_rules = (
        _changed_document_rule("flaky", lambda document, _root: _flaky_diagnostics(document)),
        _changed_document_rule("stable", lambda document, _root: _stable_diagnostics(document)),
    )
    lint_report = _lint_documents(repository_root, all_documents, all_rules)
    assert lint_report.failed_rules == ("flaky",)
    assert lint_report.executed_rules == ("stable",)
    assert lint_report.exit_code == INCOMPLETE_EXIT_CODE
    assert [each_rule.rule_id for each_rule in lint_report.diagnostics] == [
        "stable",
        "stable",
    ]


def test_process_interrupt_is_not_swallowed(tmp_path: Path) -> None:
    repository_root = tmp_path.resolve()

    def interrupt_diagnostics(
        document: Document, repository_root: Path | None = None
    ) -> tuple[Diagnostic, ...]:
        del document, repository_root
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _lint_documents(
            repository_root,
            (_source_document("pkg/mod.py"),),
            (_changed_document_rule("interrupt", interrupt_diagnostics),),
        )
