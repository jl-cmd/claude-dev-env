"""Behavioral tests for the gate_running parts module."""

from pathlib import Path

import pytest
from code_rules_gate_parts import gate_running, git_blob_readers


def _clean_validate(_content: str, _path: str, _prior: str = "", **_kwargs: object) -> list[str]:
    return []


def _dirty_validate(_content: str, _path: str, _prior: str = "", **_kwargs: object) -> list[str]:
    return ["Line 1: bad"]


def _install_eligibility_walk_counter(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Wrap ``_eligible_resolved_paths`` to tally how many walks a run makes."""
    walk_count_holder = [0]
    real_eligible_resolved_paths = gate_running._eligible_resolved_paths

    def counting_eligible_resolved_paths(
        all_file_paths: list[Path],
        repository_root: Path,
        should_read_staged_content: bool,
    ) -> list[Path]:
        walk_count_holder[0] += 1
        return real_eligible_resolved_paths(
            all_file_paths, repository_root, should_read_staged_content
        )

    monkeypatch.setattr(
        gate_running, "_eligible_resolved_paths", counting_eligible_resolved_paths
    )
    return walk_count_holder


def test_run_gate_resolves_eligible_paths_once_per_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One ``run_gate`` call walks the eligible file set exactly once.

    Deriving the inspected-file count from a second walk of the file set would
    re-run the eligibility probe on every candidate — in staged mode a wasted
    ``git cat-file -e`` subprocess per file. Counting the walks proves the set
    is resolved a single time.
    """
    first_module = tmp_path / "first_module.py"
    second_module = tmp_path / "second_module.py"
    first_module.write_text("first_count = 1\n", encoding="utf-8")
    second_module.write_text("second_count = 2\n", encoding="utf-8")

    walk_count_holder = _install_eligibility_walk_counter(monkeypatch)
    gate_running.run_gate(
        _clean_validate,
        [first_module, second_module],
        tmp_path,
        all_added_lines_by_path=None,
    )

    assert walk_count_holder[0] == 1


def test_run_gate_reports_inspected_count_for_clean_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module_path = tmp_path / "clean.py"
    module_path.write_text("value = 1\n", encoding="utf-8")

    exit_code = gate_running.run_gate(
        _clean_validate, [module_path], tmp_path, all_added_lines_by_path=None
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "inspected 1 file(s)" in captured.err


def test_run_gate_blocks_when_validate_reports_issue(tmp_path: Path) -> None:
    module_path = tmp_path / "dirty.py"
    module_path.write_text("value = 1\n", encoding="utf-8")

    exit_code = gate_running.run_gate(
        _dirty_validate, [module_path], tmp_path, all_added_lines_by_path=None
    )

    assert exit_code == 1


def test_print_violation_section_groups_by_relative_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module_path = (tmp_path / "module.py").resolve()

    gate_running.print_violation_section("HEADER", {module_path: ["Line 1: issue"]}, tmp_path)

    captured = capsys.readouterr()
    assert "HEADER" in captured.err
    assert "Line 1: issue" in captured.err


def test_run_gate_prefetches_prior_content_with_one_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One run_gate call issues a single HEAD batch for every eligible file."""
    first_module = tmp_path / "first_module.py"
    second_module = tmp_path / "second_module.py"
    first_module.write_text("first_count = 1\n", encoding="utf-8")
    second_module.write_text("second_count = 2\n", encoding="utf-8")

    batch_call_count = [0]
    single_file_call_count = [0]
    real_batch = git_blob_readers.read_prior_committed_contents_batch
    real_single = git_blob_readers.read_prior_committed_content

    def counting_batch(
        repository_root: Path, all_relative_path_posix: list[str]
    ) -> dict[str, str]:
        batch_call_count[0] += 1
        return real_batch(repository_root, all_relative_path_posix)

    def counting_single(repository_root: Path, relative_path_posix: str) -> str:
        single_file_call_count[0] += 1
        return real_single(repository_root, relative_path_posix)

    monkeypatch.setattr(
        gate_running, "read_prior_committed_contents_batch", counting_batch
    )
    monkeypatch.setattr(gate_running, "read_prior_committed_content", counting_single)

    gate_running.run_gate(
        _clean_validate,
        [first_module, second_module],
        tmp_path,
        all_added_lines_by_path=None,
    )

    assert batch_call_count[0] == 1
    assert single_file_call_count[0] == 0


def test_run_gate_prefetches_staged_content_batch_in_staged_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staged mode issues one staged batch in addition to the HEAD batch."""
    module_path = tmp_path / "staged_module.py"
    module_path.write_text("value = 1\n", encoding="utf-8")

    staged_batch_call_count = [0]
    staged_single_call_count = [0]

    def counting_staged_batch(
        repository_root: Path, all_relative_path_posix: list[str]
    ) -> dict[str, str | None]:
        staged_batch_call_count[0] += 1
        return {each_path: "value = 1\n" for each_path in all_relative_path_posix}

    def counting_staged_single(
        repository_root: Path, relative_path_posix: str
    ) -> str | None:
        staged_single_call_count[0] += 1
        return "value = 1\n"

    def always_staged(
        repository_root: Path, relative_path_posix: str
    ) -> bool:
        return True

    monkeypatch.setattr(
        gate_running, "read_staged_contents_batch", counting_staged_batch
    )
    monkeypatch.setattr(gate_running, "read_staged_content", counting_staged_single)
    monkeypatch.setattr(gate_running, "staged_blob_exists", always_staged)
    monkeypatch.setattr(
        gate_running,
        "read_prior_committed_contents_batch",
        lambda repository_root, all_relative_path_posix: {
            each_path: "" for each_path in all_relative_path_posix
        },
    )

    exit_code = gate_running.run_gate(
        _clean_validate,
        [module_path],
        tmp_path,
        all_added_lines_by_path=None,
        should_read_staged_content=True,
    )

    assert exit_code == 0
    assert staged_batch_call_count[0] == 1
    assert staged_single_call_count[0] == 0
