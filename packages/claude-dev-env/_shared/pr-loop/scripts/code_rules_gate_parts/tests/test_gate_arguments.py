"""Behavioral tests for the gate_arguments parts module."""

from pathlib import Path

from code_rules_gate_parts import gate_arguments


def test_parse_arguments_reads_staged_base_and_repo_root() -> None:
    arguments = gate_arguments.parse_arguments(
        ["--staged", "--base", "main", "--repo-root", "/tmp/repo"]
    )
    assert arguments.staged is True
    assert arguments.base == "main"
    assert arguments.repo_root == Path("/tmp/repo")


def test_parse_arguments_collects_only_under_and_paths() -> None:
    arguments = gate_arguments.parse_arguments(
        ["--only-under", "pkg", "--only-under", "lib", "a.py", "b.py"]
    )
    assert arguments.only_under == ["pkg", "lib"]
    assert arguments.paths == [Path("a.py"), Path("b.py")]


def test_parse_arguments_defaults_base_to_origin_main() -> None:
    arguments = gate_arguments.parse_arguments([])
    assert arguments.base == "origin/main"
    assert arguments.staged is False
    assert arguments.only_under == []
