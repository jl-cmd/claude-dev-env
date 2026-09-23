"""Behavioral tests for the fix pull request test-proof check.

Every case drives a git repository under ``tmp_path`` and a pytest subprocess,
the same shape the CI job runs.
"""

from pathlib import Path

import pytest

import fix_pr_test_proof
from code_rules_gate_parts.tests._repo_test_helpers import (
    repository_with_root_pytest_config,
    run_git,
)

BUGGY_PRODUCTION_TEXT = (
    "def add(left: int, right: int) -> int:\n    return left - right\n"
)
FIXED_PRODUCTION_TEXT = (
    "def add(left: int, right: int) -> int:\n    return left + right\n"
)
PROOF_TEST_TEXT = (
    "from calc import add\n\n\ndef test_add_sums_both_operands() -> None:\n"
    "    assert add(1, 2) == 3\n"
)
ALWAYS_PASSING_TEST_TEXT = (
    "def test_nothing_in_particular() -> None:\n    assert True\n"
)


def _commit_files(repository_root: Path, all_file_texts: dict[str, str]) -> None:
    for each_relative_path, each_text in all_file_texts.items():
        file_path = repository_root / each_relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(each_text, encoding="utf-8")
    run_git(repository_root, "add", "-A")
    run_git(repository_root, "commit", "--no-verify", "-m", "change")


def _head_revision(repository_root: Path) -> str:
    return run_git(repository_root, "rev-parse", "HEAD").stdout.decode().strip()


def _repository_at_buggy_base(tmp_path: Path) -> tuple[Path, str]:
    repository_root = repository_with_root_pytest_config(tmp_path)
    _commit_files(repository_root, {"pkg/calc.py": BUGGY_PRODUCTION_TEXT})
    return repository_root, _head_revision(repository_root)


def _run_check(repository_root: Path, title: str, base_revision: str) -> int:
    return fix_pr_test_proof.main(
        [
            "--title",
            title,
            "--base",
            base_revision,
            "--repository-root",
            str(repository_root),
        ]
    )


def test_a_title_outside_the_fix_type_passes(tmp_path: Path) -> None:
    repository_root, base_revision = _repository_at_buggy_base(tmp_path)
    _commit_files(repository_root, {"pkg/calc.py": FIXED_PRODUCTION_TEXT})

    assert _run_check(repository_root, "feat: add sums", base_revision) == 0


def test_a_fix_that_changes_no_production_code_passes(tmp_path: Path) -> None:
    repository_root, base_revision = _repository_at_buggy_base(tmp_path)
    _commit_files(repository_root, {"docs/notes.md": "# Notes\n"})

    assert _run_check(repository_root, "fix(docs): correct a link", base_revision) == 0


def test_a_fix_with_no_changed_test_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository_root, base_revision = _repository_at_buggy_base(tmp_path)
    _commit_files(repository_root, {"pkg/calc.py": FIXED_PRODUCTION_TEXT})

    assert _run_check(repository_root, "fix: sum operands", base_revision) == 1
    assert "no Python test" in capsys.readouterr().err


def test_a_fix_whose_test_fails_on_base_and_passes_on_head_passes(
    tmp_path: Path,
) -> None:
    repository_root, base_revision = _repository_at_buggy_base(tmp_path)
    _commit_files(
        repository_root,
        {"pkg/calc.py": FIXED_PRODUCTION_TEXT, "pkg/test_calc.py": PROOF_TEST_TEXT},
    )

    assert _run_check(repository_root, "fix(calc): sum operands", base_revision) == 0


def test_a_fix_whose_changed_test_also_passes_on_base_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository_root, base_revision = _repository_at_buggy_base(tmp_path)
    _commit_files(
        repository_root,
        {
            "pkg/calc.py": FIXED_PRODUCTION_TEXT,
            "pkg/test_calc.py": ALWAYS_PASSING_TEST_TEXT,
        },
    )

    assert _run_check(repository_root, "fix!: sum operands", base_revision) == 1
    assert "passes on the base" in capsys.readouterr().err


def test_a_fix_whose_changed_test_fails_on_head_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository_root, base_revision = _repository_at_buggy_base(tmp_path)
    _commit_files(
        repository_root,
        {"pkg/test_calc.py": PROOF_TEST_TEXT, "pkg/extra.py": "VALUE = 1\n"},
    )

    assert _run_check(repository_root, "fix: sum operands", base_revision) == 1
    assert "fails on the head" in capsys.readouterr().err
