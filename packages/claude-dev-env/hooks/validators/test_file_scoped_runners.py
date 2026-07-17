"""Tests for the file-scoped validator batch and its fail-closed behavior."""

from pathlib import Path

import pytest

from . import file_scoped_runners
from .file_scoped_runners import run_file_scoped_validators
from .validator_result import ValidatorResult


class TestFileScopedValidatorFaultFailsClosed:
    def test_one_raising_validator_fails_closed_without_killing_the_batch(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def raise_validator_fault(_files: list[Path]) -> ValidatorResult:
            raise RuntimeError("anti-pattern check crashed")

        monkeypatch.setattr(
            file_scoped_runners,
            "run_python_antipattern_checks",
            raise_validator_fault,
        )
        probe_file = tmp_path / "probe_module.py"
        probe_file.write_text("answer = 1\n", encoding="utf-8")

        all_results = run_file_scoped_validators([probe_file])

        faulted_results = [
            each_result
            for each_result in all_results
            if each_result.name == "Python Anti-patterns"
        ]
        assert len(all_results) == 14
        assert len(faulted_results) == 1
        assert faulted_results[0].passed is False
        assert faulted_results[0].skipped is False
        assert "write blocked" in faulted_results[0].output.lower()
