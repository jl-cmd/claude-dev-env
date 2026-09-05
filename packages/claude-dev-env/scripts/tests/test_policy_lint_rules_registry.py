"""Registry, grouping, and configuration tests for policy lint."""

from __future__ import annotations

import json
import subprocess
import types
from pathlib import Path, PurePosixPath

import pytest
from policy_lint import adapters, registry
from policy_lint.engine import lint
from policy_lint.model import (
    ChangeSetRule,
    Document,
    DocumentRule,
    DocumentSet,
    LintRequest,
    SelectionKind,
)

_FUNCTION_SOURCE = "def work() -> None:\n    pass\n"
_CHANGED_RULE_SETS = frozenset({"changed"})


def _rule_named(rule_id: str) -> DocumentRule:
    for each_rule in registry.default_registry():
        if each_rule.rule_id == rule_id and isinstance(each_rule, DocumentRule):
            return each_rule
    raise AssertionError(rule_id)


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


def _commit_repository(repository_root: Path, message: str) -> None:
    subprocess.run(
        ("git", "config", "user.email", "test@example.com"),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "config", "user.name", "Test"),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "add", "-A"), cwd=repository_root, check=True, capture_output=True
    )
    subprocess.run(
        ("git", "commit", "-m", message),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def _stage_terminology_change(
    repository_root: Path,
    base_source: str,
    current_source: str,
    documentation_text: str,
) -> None:
    _ensure_git_repository(repository_root)
    source_path = repository_root / "src" / "quota.py"
    source_path.parent.mkdir()
    source_path.write_text(base_source, encoding="utf-8")
    _commit_repository(repository_root, "base")
    source_path.write_text(current_source, encoding="utf-8")
    documentation_path = repository_root / "docs" / "README.md"
    documentation_path.parent.mkdir()
    documentation_path.write_text(documentation_text, encoding="utf-8")
    subprocess.run(
        ("git", "add", "-A"), cwd=repository_root, check=True, capture_output=True
    )


def _terminology_rule() -> ChangeSetRule:
    terminology_rule = next(
        each_rule
        for each_rule in registry.default_registry()
        if each_rule.rule_id == "terminology-sweep"
    )
    assert isinstance(terminology_rule, ChangeSetRule)
    return terminology_rule


def test_hook_format_accepts_claude_settings() -> None:
    settings_document = Document.from_text(".claude/settings.json", "{}")
    hooks_document = Document.from_text("hooks/hooks.json", "{}")
    format_rule = _rule_named("hook-format")
    configuration_rule = _rule_named("hook-configuration")
    assert format_rule.accepts(settings_document) is True
    assert format_rule.accepts(hooks_document) is False
    assert configuration_rule.accepts(hooks_document) is True
    assert configuration_rule.accepts(settings_document) is False


def test_workflow_substitution_accepts_workflow_js_suffix() -> None:
    workflow_document = Document.from_text("packages/foo/bar.workflow.js", "loop")
    directory_document = Document.from_text("docs/workflow/readme.md", "loop")
    assert adapters.accepts_workflow(workflow_document) is True
    assert adapters.accepts_workflow(directory_document) is False


def test_open_questions_cover_repository_and_claude_plans() -> None:
    docs_plan = Document.from_text("docs/plans/packet.md", "# Plan\n")
    claude_plan = Document.from_text(".claude/plans/packet.md", "# Plan\n")
    other_markdown = Document.from_text("docs/notes.md", "# Notes\n")
    assert adapters.accepts_plans(docs_plan) is True
    assert adapters.accepts_plans(claude_plan) is True
    assert adapters.accepts_plans(other_markdown) is False


def test_open_question_diagnostics_scan_claude_plans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_hooks_module(module_name: str) -> object:
        if not module_name:
            raise AssertionError("missing module")
        return types.SimpleNamespace(_content_has_open_questions=lambda text: True)

    monkeypatch.setattr(adapters, "_hooks_module", fake_hooks_module)
    all_diagnostics = adapters.open_question_diagnostics(
        Document.from_text(".claude/plans/packet.md", "## Open Questions\n"),
        tmp_path,
    )
    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].rule_id == "open-questions"


def test_test_pairing_diagnostics_reports_unmatched_changed_production_file(
    tmp_path: Path,
) -> None:
    document_set = DocumentSet(
        (Document.from_text("src/feature.py", _FUNCTION_SOURCE),),
        SelectionKind.STAGED,
        tmp_path,
    )
    all_diagnostics = adapters.test_pairing_diagnostics(document_set)
    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].location is not None
    assert all_diagnostics[0].location.path == PurePosixPath("src/feature.py")


def test_test_pairing_diagnostics_exempts_constants_only_python_modules(
    tmp_path: Path,
) -> None:
    document_set = DocumentSet(
        (
            Document.from_text(
                "hooks_constants/tool_names.py",
                "TOOL_NAME: str = \"tool\"\n",
            ),
        ),
        SelectionKind.STAGED,
        tmp_path,
    )
    assert adapters.test_pairing_diagnostics(document_set) == ()


def test_test_pairing_diagnostics_accepts_changed_matching_test(tmp_path: Path) -> None:
    document_set = DocumentSet(
        (
            Document.from_text("src/feature.py", _FUNCTION_SOURCE),
            Document.from_text("tests/test_feature.py", _FUNCTION_SOURCE),
        ),
        SelectionKind.BASE,
        tmp_path,
    )
    assert adapters.test_pairing_diagnostics(document_set) == ()


@pytest.mark.parametrize(
    ("production_path", "test_path"),
    (
        ("scripts/policy_lint/adapters.py", "scripts/tests/test_policy_lint_rules.py"),
        (
            "scripts/policy_lint/selection.py",
            "scripts/tests/test_policy_lint_selection.py",
        ),
        (
            "hooks/validators/run_all_validators.py",
            "hooks/validators/test_run_all_validators_integration.py",
        ),
        ("bin/install-plan.mjs", "bin/install.plan.test.mjs"),
    ),
)
def test_test_pairing_diagnostics_accepts_grouped_families(
    tmp_path: Path, production_path: str, test_path: str
) -> None:
    document_set = DocumentSet(
        (
            Document.from_text(production_path, _FUNCTION_SOURCE),
            Document.from_text(test_path, _FUNCTION_SOURCE),
        ),
        SelectionKind.STAGED,
        tmp_path,
    )
    assert adapters.test_pairing_diagnostics(document_set) == ()


def test_test_pairing_diagnostics_rejects_a_different_family(tmp_path: Path) -> None:
    document_set = DocumentSet(
        (
            Document.from_text("src/feature.py", _FUNCTION_SOURCE),
            Document.from_text("tests/test_feature_helper.py", _FUNCTION_SOURCE),
        ),
        SelectionKind.STAGED,
        tmp_path,
    )
    all_diagnostics = adapters.test_pairing_diagnostics(document_set)
    assert len(all_diagnostics) == 1


def test_test_pairing_diagnostics_recognizes_spec_test_paths(tmp_path: Path) -> None:
    document_set = DocumentSet(
        (
            Document.from_text("src/widget.ts", _FUNCTION_SOURCE),
            Document.from_text("tests/widget.spec.ts", _FUNCTION_SOURCE),
        ),
        SelectionKind.STAGED,
        tmp_path,
    )
    assert adapters.test_pairing_diagnostics(document_set) == ()


def test_hook_configuration_diagnostics_rejects_registered_action_boundary_path(
    tmp_path: Path,
) -> None:
    configuration_document = Document.from_text(
        "hooks/hooks.json",
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"hooks": [{"command": "hooks/blocking/deny.py"}]}
                    ]
                }
            }
        ),
    )
    all_diagnostics = adapters.hook_configuration_diagnostics(
        configuration_document, tmp_path
    )
    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].rule_id == "hook-configuration"


def test_hook_configuration_diagnostics_ignore_description_text(tmp_path: Path) -> None:
    configuration_document = Document.from_text(
        "hooks/hooks.json",
        json.dumps({"description": "blocking safety controls", "hooks": {}}),
    )
    assert adapters.hook_configuration_diagnostics(configuration_document, tmp_path) == ()


def test_hook_configuration_diagnostics_ignore_task_path(tmp_path: Path) -> None:
    configuration_document = Document.from_text(
        "hooks/hooks.json",
        json.dumps({"hooks": {"PostToolUse": [{"command": "task_runner.py"}]}}),
    )
    assert adapters.hook_configuration_diagnostics(configuration_document, tmp_path) == ()


def test_registry_omits_native_ruff_mypy_javascript_adapters() -> None:
    all_rule_ids = {each_rule.rule_id for each_rule in registry.default_registry()}
    assert "ruff" not in all_rule_ids
    assert "mypy" not in all_rule_ids
    assert "eslint" not in all_rule_ids
    assert "javascript" not in all_rule_ids


def test_registry_registers_unique_python_validator_rule() -> None:
    validator_rule = _rule_named("validators")
    assert validator_rule.accepts(Document.from_text("module.py", _FUNCTION_SOURCE))
    assert not validator_rule.accepts(Document.from_text("module.ts", _FUNCTION_SOURCE))


def test_registry_registers_terminology_change_set_rule() -> None:
    terminology_rule = _terminology_rule()
    assert terminology_rule.rule_sets == _CHANGED_RULE_SETS
    assert terminology_rule.selections == frozenset(
        {SelectionKind.STAGED, SelectionKind.BASE}
    )


def test_registry_runs_test_pairing_for_staged_and_base_changes() -> None:
    test_pairing_rule = next(
        each_rule
        for each_rule in registry.default_registry()
        if each_rule.rule_id == "test-pairing"
    )
    assert isinstance(test_pairing_rule, ChangeSetRule)
    assert test_pairing_rule.selections == frozenset(
        {SelectionKind.STAGED, SelectionKind.BASE}
    )


def test_terminology_rule_reports_cross_surface_path_and_line(
    tmp_path: Path,
) -> None:
    _stage_terminology_change(
        tmp_path,
        "baseline = 1\n",
        "premium_request_interactions = 5\n",
        "Quota fields use one name.\n"
        "The premium-request-budget field gates the run.\n",
    )
    lint_report = lint(LintRequest.staged(tmp_path), all_registry=(_terminology_rule(),))

    assert len(lint_report.diagnostics) == 1
    diagnostic = lint_report.diagnostics[0]
    assert diagnostic.rule_id == "terminology-sweep"
    assert diagnostic.location is not None
    assert diagnostic.location.path == PurePosixPath("docs/README.md")
    assert diagnostic.location.start_line == 2


def test_terminology_rule_suppresses_identifier_present_in_prior_tree(
    tmp_path: Path,
) -> None:
    _stage_terminology_change(
        tmp_path,
        "premium_request_interactions = 5\n",
        "premium_request_interactions = 5\n"
        "premium_request_interactions = 6\n",
        "The premium-request-budget field gates the run.\n",
    )
    lint_report = lint(LintRequest.staged(tmp_path), all_registry=(_terminology_rule(),))

    assert lint_report.diagnostics == ()


def test_terminology_rule_reports_committed_changes_from_base(
    tmp_path: Path,
) -> None:
    _ensure_git_repository(tmp_path)
    source_path = tmp_path / "src" / "quota.py"
    documentation_path = tmp_path / "docs" / "README.md"
    source_path.parent.mkdir()
    documentation_path.parent.mkdir()
    source_path.write_text("baseline = 1\n", encoding="utf-8")
    documentation_path.write_text("Baseline quota text.\n", encoding="utf-8")
    _commit_repository(tmp_path, "base")
    comparison_revision = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_path.write_text(
        "baseline = 1\npremium_request_interactions = 5\n",
        encoding="utf-8",
    )
    _commit_repository(tmp_path, "identifier")
    documentation_path.write_text(
        "The premium-request-budget field gates the run.\n",
        encoding="utf-8",
    )
    _commit_repository(tmp_path, "documentation")
    (tmp_path / "staged.txt").write_text("unrelated index content\n", encoding="utf-8")
    subprocess.run(
        ("git", "add", "--", "staged.txt"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    lint_report = lint(
        LintRequest.base(tmp_path, comparison_revision),
        all_registry=(_terminology_rule(),),
    )

    assert len(lint_report.diagnostics) == 1
    assert lint_report.diagnostics[0].location is not None
    assert lint_report.diagnostics[0].location.path == PurePosixPath("docs/README.md")


def test_terminology_base_uses_worktree_while_staged_uses_index(
    tmp_path: Path,
) -> None:
    _ensure_git_repository(tmp_path)
    source_path = tmp_path / "src" / "quota.py"
    documentation_path = tmp_path / "docs" / "README.md"
    source_path.parent.mkdir()
    documentation_path.parent.mkdir()
    source_path.write_text("baseline = 1\n", encoding="utf-8")
    documentation_path.write_text("Baseline quota text.\n", encoding="utf-8")
    _commit_repository(tmp_path, "base")
    comparison_revision = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_path.write_text(
        "baseline = 1\npremium_request_interactions = 5\n",
        encoding="utf-8",
    )
    _commit_repository(tmp_path, "identifier")
    documentation_path.write_text(
        "The premium-request-budget field gates the run.\n",
        encoding="utf-8",
    )
    _commit_repository(tmp_path, "documentation")
    source_path.write_text(
        "baseline = 1\n"
        "premium_request_interactions = 5\n"
        "another_request_total = 2\n",
        encoding="utf-8",
    )
    documentation_path.write_text(
        "The another-request-budget field gates the run.\n",
        encoding="utf-8",
    )
    subprocess.run(
        ("git", "add", "-A"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    documentation_path.write_text(
        "The another-request-total field gates the run.\n",
        encoding="utf-8",
    )

    base_report = lint(
        LintRequest.base(tmp_path, comparison_revision),
        all_registry=(_terminology_rule(),),
    )
    staged_report = lint(
        LintRequest.staged(tmp_path),
        all_registry=(_terminology_rule(),),
    )

    assert base_report.diagnostics == ()
    assert len(staged_report.diagnostics) == 1
    assert staged_report.diagnostics[0].location is not None
    assert staged_report.diagnostics[0].location.path == PurePosixPath(
        "docs/README.md"
    )


def test_terminology_base_suppresses_identifier_present_in_comparison_base(
    tmp_path: Path,
) -> None:
    _ensure_git_repository(tmp_path)
    source_path = tmp_path / "src" / "quota.py"
    documentation_path = tmp_path / "docs" / "README.md"
    source_path.parent.mkdir()
    documentation_path.parent.mkdir()
    source_path.write_text(
        "premium_request_interactions = 5\n",
        encoding="utf-8",
    )
    documentation_path.write_text("Baseline quota text.\n", encoding="utf-8")
    _commit_repository(tmp_path, "base")
    comparison_revision = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_path.write_text(
        "premium_request_interactions = 5\n"
        "premium_request_interactions = 6\n",
        encoding="utf-8",
    )
    documentation_path.write_text(
        "The premium-request-budget field gates the run.\n",
        encoding="utf-8",
    )
    _commit_repository(tmp_path, "existing identifier")

    lint_report = lint(
        LintRequest.base(tmp_path, comparison_revision),
        all_registry=(_terminology_rule(),),
    )

    assert lint_report.diagnostics == ()


def test_terminology_base_handles_renames_and_deletions(
    tmp_path: Path,
) -> None:
    _ensure_git_repository(tmp_path)
    old_source_path = tmp_path / "src" / "old_quota.py"
    deleted_documentation_path = tmp_path / "docs" / "obsolete.md"
    old_source_path.parent.mkdir()
    deleted_documentation_path.parent.mkdir()
    old_source_path.write_text("baseline = 1\n", encoding="utf-8")
    deleted_documentation_path.write_text("Obsolete quota text.\n", encoding="utf-8")
    _commit_repository(tmp_path, "base")
    comparison_revision = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    new_source_path = tmp_path / "src" / "new_quota.py"
    subprocess.run(
        ("git", "mv", "--", str(old_source_path), str(new_source_path)),
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    new_source_path.write_text(
        "baseline = 1\npremium_request_interactions = 5\n",
        encoding="utf-8",
    )
    deleted_documentation_path.unlink()
    documentation_path = tmp_path / "docs" / "README.md"
    documentation_path.write_text(
        "The premium-request-budget field gates the run.\n",
        encoding="utf-8",
    )
    _commit_repository(tmp_path, "rename and delete")

    lint_report = lint(
        LintRequest.base(tmp_path, comparison_revision),
        all_registry=(_terminology_rule(),),
    )

    assert len(lint_report.diagnostics) == 1
    assert lint_report.diagnostics[0].location is not None
    assert lint_report.diagnostics[0].location.path == PurePosixPath(
        "docs/README.md"
    )


def test_terminology_rule_skips_file_selection(tmp_path: Path) -> None:
    document_set = DocumentSet(
        (Document.from_text("docs/README.md", "text\n"),),
        SelectionKind.FILES,
        tmp_path,
    )
    assert adapters.terminology_diagnostics(document_set) == ()


def test_lint_keeps_skipped_rules_out_of_executed_rules(tmp_path: Path) -> None:
    skipped_rule = DocumentRule(
        "skipped",
        _CHANGED_RULE_SETS,
        lambda _document: False,
        lambda _document, _root: (),
    )
    _ensure_git_repository(tmp_path)
    document_set = DocumentSet(
        (Document.from_text("pkg/mod.py", "x = 1\n"),),
        SelectionKind.TEXT,
        tmp_path,
    )
    request = LintRequest(tmp_path, document_set)
    all_rules_report = lint(request, all_registry=(skipped_rule,))
    assert all_rules_report.executed_rules == ()
    assert all_rules_report.skipped_rules == ("skipped",)
