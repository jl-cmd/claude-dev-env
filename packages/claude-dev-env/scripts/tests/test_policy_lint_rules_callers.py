"""Tests for the uncalled-new-file rule over a change set."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from policy_lint import adapter_callers, registry
from policy_lint.model import (
    ChangeSetRule,
    ContentOrigin,
    Document,
    DocumentSet,
    SelectionKind,
)

_PACKAGE = "packages/claude-dev-env"
_NEW_SCRIPT = f"{_PACKAGE}/scripts/lonely_watcher.py"


def _write(repository_root: Path, relative_path: str, text: str) -> None:
    target = repository_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, "utf-8")


def _added(
    relative_path: str, prior_text: str | None = None, text: str = "print('hi')\n"
) -> Document:
    return Document(
        PurePosixPath(relative_path),
        text,
        prior_text,
        None,
        ContentOrigin.REVISION_DIFF,
    )


def _messages(
    repository_root: Path,
    all_documents: tuple[Document, ...],
    selection: SelectionKind = SelectionKind.BASE,
) -> tuple[str, ...]:
    document_set = DocumentSet(all_documents, selection, repository_root)
    return tuple(
        each_diagnostic.message
        for each_diagnostic in adapter_callers.uncalled_new_file_diagnostics(
            document_set
        )
    )


def test_should_report_a_new_script_only_its_own_test_names(tmp_path: Path) -> None:
    _write(tmp_path, _NEW_SCRIPT, "print('hi')\n")
    _write(
        tmp_path,
        f"{_PACKAGE}/scripts/tests/test_lonely_watcher.py",
        "import lonely_watcher\n",
    )
    _write(tmp_path, f"{_PACKAGE}/CHANGELOG.md", "added lonely_watcher\n")
    _write(tmp_path, f"{_PACKAGE}/README.md", "| lonely_watcher | x |\n")
    _write(tmp_path, f"{_PACKAGE}/bin/ever-shipped-skills.mjs", "'lonely_watcher'\n")

    all_messages = _messages(tmp_path, (_added(_NEW_SCRIPT),))

    assert len(all_messages) == 1
    assert "lonely_watcher" in all_messages[0]


def test_should_pass_a_new_script_a_workflow_runs(tmp_path: Path) -> None:
    _write(tmp_path, _NEW_SCRIPT, "print('hi')\n")
    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        f"run: python {_NEW_SCRIPT}\n",
    )

    assert _messages(tmp_path, (_added(_NEW_SCRIPT),)) == ()


def test_should_pass_a_new_hook_that_hooks_json_registers(tmp_path: Path) -> None:
    hook_path = f"{_PACKAGE}/hooks/advisory/quiet_guard.py"
    _write(tmp_path, hook_path, "")
    _write(
        tmp_path,
        f"{_PACKAGE}/hooks/hooks.json",
        '{"command": "python hooks/advisory/quiet_guard.py"}',
    )

    assert _messages(tmp_path, (_added(hook_path),)) == ()


def test_should_ignore_a_file_that_existed_before_the_change(tmp_path: Path) -> None:
    _write(tmp_path, _NEW_SCRIPT, "print('hi')\n")

    assert _messages(tmp_path, (_added(_NEW_SCRIPT, "old\n"),)) == ()


def test_should_ignore_new_tests_and_files_outside_code_folders(
    tmp_path: Path,
) -> None:
    test_path = f"{_PACKAGE}/scripts/tests/test_orphan.py"
    rule_path = f"{_PACKAGE}/rules/orphan.md"
    _write(tmp_path, test_path, "")
    _write(tmp_path, rule_path, "")

    assert _messages(tmp_path, (_added(test_path), _added(rule_path))) == ()


def test_should_not_count_a_longer_name_that_contains_the_stem(
    tmp_path: Path,
) -> None:
    _write(tmp_path, _NEW_SCRIPT, "print('hi')\n")
    _write(tmp_path, f"{_PACKAGE}/scripts/runner.py", "import lonely_watcher_v2\n")

    assert len(_messages(tmp_path, (_added(_NEW_SCRIPT),))) == 1


def test_should_run_on_staged_and_base_selections() -> None:
    uncalled_rule = next(
        each_rule
        for each_rule in registry.default_registry()
        if each_rule.rule_id == "uncalled-new-file"
    )

    assert isinstance(uncalled_rule, ChangeSetRule)
    assert uncalled_rule.selections == frozenset(
        {SelectionKind.STAGED, SelectionKind.BASE}
    )


def test_should_report_new_ci_and_tools_helpers_only_tests_name(
    tmp_path: Path,
) -> None:
    ci_helper = ".github/ci/lonely_router.py"
    tools_helper = "tools/lonely_archiver.py"
    _write(tmp_path, ci_helper, "print('hi')\n")
    _write(tmp_path, tools_helper, "print('hi')\n")
    _write(tmp_path, ".github/ci/test_lonely_router.py", "import lonely_router\n")

    all_messages = _messages(tmp_path, (_added(ci_helper), _added(tools_helper)))

    assert len(all_messages) == 2


def test_should_pass_a_new_module_that_a_called_new_script_imports(
    tmp_path: Path,
) -> None:
    constants_path = f"{_PACKAGE}/scripts/constants/lonely_watcher_constants.py"
    script_text = "from constants.lonely_watcher_constants import LIMIT\n"
    _write(tmp_path, _NEW_SCRIPT, script_text)
    _write(tmp_path, constants_path, "LIMIT = 3\n")
    _write(tmp_path, ".github/workflows/ci.yml", f"run: python {_NEW_SCRIPT}\n")

    all_documents = (_added(_NEW_SCRIPT, text=script_text), _added(constants_path))

    assert _messages(tmp_path, all_documents) == ()


def test_should_report_a_new_module_only_an_uncalled_new_script_imports(
    tmp_path: Path,
) -> None:
    constants_path = f"{_PACKAGE}/scripts/constants/lonely_watcher_constants.py"
    script_text = "from constants.lonely_watcher_constants import LIMIT\n"
    _write(tmp_path, _NEW_SCRIPT, script_text)
    _write(tmp_path, constants_path, "LIMIT = 3\n")

    all_documents = (_added(_NEW_SCRIPT, text=script_text), _added(constants_path))

    assert len(_messages(tmp_path, all_documents)) == 2
