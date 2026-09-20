"""Behavior tests for the breaking-or-smell split in the instruction-pair check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from validate_instruction_pairs import (
    GATE_FAILED_EXIT_CODE,
    GATE_PASSED_EXIT_CODE,
    all_instruction_findings,
    run_gate,
)

_hooks_directory = str(Path(__file__).resolve().parents[1] / "hooks")
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from followup_ledger import all_recorded_findings


def initialize_repository(repository_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=repository_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Instruction tests"],
        cwd=repository_root,
        check=True,
    )


def write_valid_pair(repository_root: Path) -> None:
    (repository_root / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (repository_root / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")
    subprocess.run(
        ["git", "add", "AGENTS.md", "CLAUDE.md"], cwd=repository_root, check=True
    )


def make_import_text_wrong(repository_root: Path) -> None:
    (repository_root / "CLAUDE.md").write_bytes(b"@AGENTS.md\n\nExtra guidance.\n")


def make_git_mode_executable(repository_root: Path) -> None:
    subprocess.run(
        ["git", "update-index", "--chmod=+x", "CLAUDE.md"],
        cwd=repository_root,
        check=True,
    )


def test_a_wrong_import_text_is_a_breaking_finding(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    write_valid_pair(tmp_path)
    make_import_text_wrong(tmp_path)

    all_breaking = [
        each_finding
        for each_finding in all_instruction_findings(tmp_path)
        if each_finding.severity == "breaking"
    ]

    assert [each_finding.rule_id for each_finding in all_breaking] == [
        "instruction-import-text"
    ]


def test_a_wrong_git_mode_is_a_smell_finding(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    write_valid_pair(tmp_path)
    make_git_mode_executable(tmp_path)

    all_smells = [
        each_finding
        for each_finding in all_instruction_findings(tmp_path)
        if each_finding.severity == "smell"
    ]

    assert [each_finding.rule_id for each_finding in all_smells] == [
        "instruction-git-mode"
    ]


def test_run_gate_fails_on_a_breaking_finding(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    write_valid_pair(tmp_path)
    make_import_text_wrong(tmp_path)

    assert run_gate(tmp_path) == GATE_FAILED_EXIT_CODE


def test_run_gate_passes_a_smell_and_records_it(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    write_valid_pair(tmp_path)
    make_git_mode_executable(tmp_path)

    exit_code = run_gate(tmp_path)

    assert exit_code == GATE_PASSED_EXIT_CODE
    assert [
        each_finding.rule_id for each_finding in all_recorded_findings(tmp_path)
    ] == ["instruction-git-mode"]


def test_run_gate_records_a_smell_it_finds_beside_a_breaking_finding(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    write_valid_pair(tmp_path)
    make_import_text_wrong(tmp_path)
    make_git_mode_executable(tmp_path)

    exit_code = run_gate(tmp_path)

    assert exit_code == GATE_FAILED_EXIT_CODE
    assert [
        each_finding.rule_id for each_finding in all_recorded_findings(tmp_path)
    ] == ["instruction-git-mode"]


def test_run_gate_passes_a_valid_tree_and_records_nothing(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    write_valid_pair(tmp_path)

    exit_code = run_gate(tmp_path)

    assert exit_code == GATE_PASSED_EXIT_CODE
    assert all_recorded_findings(tmp_path) == ()
