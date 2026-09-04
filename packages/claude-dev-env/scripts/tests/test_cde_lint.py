"""Behavioral tests for the public policy-lint command."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from types import ModuleType

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

import cde_lint
from policy_lint import render as render_module
from policy_lint.model import (
    BaseChanges,
    Diagnostic,
    ExplicitFiles,
    LintReport,
    LintRequest,
    Location,
    RepositoryTree,
    Severity,
    StagedChanges,
    TextDocument,
)
from policy_lint.selection import SelectionRunFatal


def _cli_module() -> ModuleType:
    return cde_lint


def _render_module() -> ModuleType:
    return render_module


def _clean_report() -> LintReport:
    return LintReport(1, (), (), ("rule-a",), (), ())


def _located_diagnostic() -> Diagnostic:
    return Diagnostic(
        "rule-a",
        Severity.ERROR,
        "located finding",
        Location(PurePosixPath("src/app.py"), 4, 2),
    )


def _unlocated_diagnostic() -> Diagnostic:
    return Diagnostic("rule-b", Severity.WARNING, "unlocated finding")


def _mixed_report() -> LintReport:
    return LintReport(
        1,
        (_located_diagnostic(), _unlocated_diagnostic()),
        (PurePosixPath("src/app.py"),),
        ("rule-a", "rule-b"),
        (),
        (),
    )


def _run_cli(
    all_arguments: list[str],
    *,
    stdin_text: str = "",
    lint_runner: Callable[[LintRequest], LintReport],
    repository_root: Path,
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = _cli_module().main(
        all_arguments,
        stdin=io.StringIO(stdin_text),
        stdout=stdout,
        stderr=stderr,
        lint_runner=lint_runner,
        repository_root=repository_root,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _capture_request(
    all_arguments: list[str],
    repository_root: Path,
    stdin_text: str = "",
) -> LintRequest:
    captured_request: dict[str, LintRequest] = {}

    def fake_lint(request: LintRequest) -> LintReport:
        captured_request["request"] = request
        return _clean_report()

    exit_code, _, stderr_text = _run_cli(
        all_arguments,
        stdin_text=stdin_text,
        lint_runner=fake_lint,
        repository_root=repository_root,
    )
    assert exit_code == 0, stderr_text
    return captured_request["request"]


def test_should_build_explicit_files_request(tmp_path: Path) -> None:
    request = _capture_request(
        ["--files", "src/a.py", "src/b.py"],
        repository_root=tmp_path,
    )
    assert isinstance(request.source, ExplicitFiles)
    assert request.source.paths == (Path("src/a.py"), Path("src/b.py"))
    assert request.repository_root == tmp_path
    assert request.rule_sets == frozenset({"changed"})


def test_should_build_staged_request(tmp_path: Path) -> None:
    request = _capture_request(["--staged"], repository_root=tmp_path)
    assert isinstance(request.source, StagedChanges)
    assert request.rule_sets == frozenset({"changed"})


def test_should_build_base_request(tmp_path: Path) -> None:
    request = _capture_request(
        ["--base", "origin/main"],
        repository_root=tmp_path,
    )
    assert isinstance(request.source, BaseChanges)
    assert request.source.revision == "origin/main"


def test_should_build_repository_request(tmp_path: Path) -> None:
    request = _capture_request(["--repository"], repository_root=tmp_path)
    assert isinstance(request.source, RepositoryTree)
    assert request.rule_sets == frozenset({"repository"})


def test_should_read_text_as_from_stdin_not_disk(tmp_path: Path) -> None:
    buffer_path = tmp_path / "draft.py"
    buffer_path.write_text("DISK CONTENTS\n", encoding="utf-8")
    request = _capture_request(
        ["--text-as", str(buffer_path)],
        repository_root=tmp_path,
        stdin_text="EDITOR BUFFER",
    )
    assert isinstance(request.source, TextDocument)
    assert request.source.path == buffer_path
    assert request.source.text == "EDITOR BUFFER"


def test_should_reject_combined_source_flags(tmp_path: Path) -> None:
    calls: list[LintRequest] = []

    def fake_lint(request: LintRequest) -> LintReport:
        calls.append(request)
        return _clean_report()

    exit_code, _, stderr_text = _run_cli(
        ["--files", "a.py", "--staged"],
        lint_runner=fake_lint,
        repository_root=tmp_path,
    )
    assert exit_code == 2
    assert calls == []
    assert stderr_text != ""


def test_should_exit_two_when_no_source_flag(tmp_path: Path) -> None:
    exit_code, _, stderr_text = _run_cli(
        [],
        lint_runner=lambda _request: _clean_report(),
        repository_root=tmp_path,
    )
    assert exit_code == 2
    assert stderr_text != ""


def test_should_discover_repository_root_from_nested_directory(tmp_path: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()
    assert _cli_module()._discover_repository_root(nested_directory) == tmp_path.resolve()


def test_should_resolve_files_from_the_caller_directory(tmp_path: Path) -> None:
    all_arguments = _cli_module()._resolve_shell_file_arguments(
        ["--files", "nested.py", "--format", "json"], tmp_path
    )
    assert all_arguments == [
        "--files",
        str(tmp_path / "nested.py"),
        "--format",
        "json",
    ]


def test_should_resolve_text_path_from_the_caller_directory(tmp_path: Path) -> None:
    all_arguments = _cli_module()._resolve_shell_file_arguments(
        ["--text-as", "nested.py", "--format", "editor"], tmp_path
    )
    assert all_arguments == [
        "--text-as",
        str(tmp_path / "nested.py"),
        "--format",
        "editor",
    ]


def test_should_report_missing_git_as_invalid_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def missing_git(_repository_root: Path, _all_arguments: tuple[str, ...]) -> bytes:
        raise FileNotFoundError("git")

    monkeypatch.setattr(_cli_module(), "git_bytes_for", missing_git)
    with pytest.raises(_cli_module()._LintUsageError, match="Git repository"):
        _cli_module()._discover_repository_root(tmp_path)


def test_should_exit_two_for_unknown_format(tmp_path: Path) -> None:
    exit_code, _, stderr_text = _run_cli(
        ["--files", "a.py", "--format", "xml"],
        lint_runner=lambda _request: _clean_report(),
        repository_root=tmp_path,
    )
    assert exit_code == 2
    assert stderr_text != ""


def test_should_exit_two_when_selection_fails(tmp_path: Path) -> None:
    def fake_lint(request: LintRequest) -> LintReport:
        del request
        raise SelectionRunFatal("File does not exist: missing.py")

    exit_code, _, stderr_text = _run_cli(
        ["--files", "missing.py"],
        lint_runner=fake_lint,
        repository_root=tmp_path,
    )
    assert exit_code == 2
    assert "File does not exist: missing.py" in stderr_text


def test_should_exit_zero_when_the_report_is_clean(tmp_path: Path) -> None:
    exit_code, stdout_text, stderr_text = _run_cli(
        ["--staged"],
        lint_runner=lambda _request: _clean_report(),
        repository_root=tmp_path,
    )
    assert exit_code == 0
    assert stderr_text == ""
    assert stdout_text == ""


def _stage_oversized_test_file(repository_root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    oversized_path = repository_root / "tests" / "oversized.mjs"
    oversized_path.parent.mkdir()
    oversized_path.write_bytes(b"\n" * 1001)
    subprocess.run(
        ["git", "add", "--", "tests/oversized.mjs"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def _run_staged_format(
    report_format: str, repository_root: Path
) -> tuple[int, str, str]:
    return _run_cli(
        ["--staged", "--format", report_format],
        lint_runner=_cli_module().lint,
        repository_root=repository_root,
    )


def test_staged_clean_reports_keep_legacy_advisories_outside_renderer(
    tmp_path: Path,
) -> None:
    _stage_oversized_test_file(tmp_path)
    json_exit_code, json_stdout, json_stderr = _run_staged_format("json", tmp_path)
    text_exit_code, text_stdout, text_stderr = _run_staged_format("text", tmp_path)
    editor_exit_code, editor_stdout, editor_stderr = _run_staged_format(
        "editor", tmp_path
    )

    assert json_exit_code == 0
    assert json_stderr == ""
    assert json.loads(json_stdout)["diagnostics"] == []
    assert text_exit_code == 0
    assert text_stdout == ""
    assert text_stderr == ""
    assert editor_exit_code == 0
    assert editor_stdout == ""
    assert editor_stderr == ""


def test_should_exit_one_when_diagnostics_exist(tmp_path: Path) -> None:
    exit_code, stdout_text, _stderr_text = _run_cli(
        ["--files", "src/app.py"],
        lint_runner=lambda _request: _mixed_report(),
        repository_root=tmp_path,
    )
    assert exit_code == 1
    assert "located finding" in stdout_text
    assert "unlocated finding" in stdout_text


def test_should_exit_three_when_a_rule_fails(tmp_path: Path) -> None:
    failed_report = LintReport(1, (), (), (), ("rule-a",), ())
    exit_code, stdout_text, _stderr_text = _run_cli(
        ["--staged"],
        lint_runner=lambda _request: failed_report,
        repository_root=tmp_path,
    )
    assert exit_code == 3
    assert "rule-a" in stdout_text


def test_should_emit_schema_versioned_deterministic_json(tmp_path: Path) -> None:
    render_module = _render_module()
    first_text = render_module.render(_mixed_report(), render_module.ReportFormat.JSON)
    second_text = render_module.render(_mixed_report(), render_module.ReportFormat.JSON)
    assert first_text == second_text
    parsed_report = json.loads(first_text)
    assert parsed_report["schema_version"] == 1
    assert parsed_report == json.loads(
        json.dumps(parsed_report, sort_keys=True)
    )
    exit_code, stdout_text, _stderr_text = _run_cli(
        ["--files", "src/app.py", "--format", "json"],
        lint_runner=lambda _request: _mixed_report(),
        repository_root=tmp_path,
    )
    assert exit_code == 1
    assert json.loads(stdout_text) == parsed_report


def test_should_emit_only_located_diagnostics_in_editor_format(
    tmp_path: Path,
) -> None:
    render_module = _render_module()
    rendered_text = render_module.render(
        _mixed_report(), render_module.ReportFormat.EDITOR
    )
    assert "src/app.py:4:2:" in rendered_text
    assert "located finding" in rendered_text
    assert "unlocated finding" not in rendered_text
    exit_code, stdout_text, _stderr_text = _run_cli(
        ["--files", "src/app.py", "--format", "editor"],
        lint_runner=lambda _request: _mixed_report(),
        repository_root=tmp_path,
    )
    assert exit_code == 1
    assert "src/app.py:4:2:" in stdout_text
    assert "unlocated finding" not in stdout_text
