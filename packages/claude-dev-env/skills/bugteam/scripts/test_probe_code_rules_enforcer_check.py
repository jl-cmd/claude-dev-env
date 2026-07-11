"""Tests for probe_code_rules_enforcer_check."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

import probe_code_rules_enforcer_check as probe_module
from probe_code_rules_enforcer_check import main, run_probe


class _FakeEnforcerModule:
    @staticmethod
    def check_dummy(content: str, reported_path: str) -> list[str]:
        if "trigger" in content:
            return [f"{reported_path}: trigger detected"]
        return []


def _install_fake_loader(
    monkeypatch: pytest.MonkeyPatch,
    fake_module: Any,
) -> None:
    monkeypatch.setattr(probe_module, "_load_enforcer_module", lambda: fake_module)


def test_run_probe_returns_check_function_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_loader(monkeypatch, _FakeEnforcerModule())
    fixture = tmp_path / "fixture.py"
    fixture.write_text("trigger me", encoding="utf-8")
    issues = run_probe("check_dummy", str(fixture), "reported.py")
    assert issues == ["reported.py: trigger detected"]


def test_run_probe_raises_when_check_function_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_loader(monkeypatch, _FakeEnforcerModule())
    fixture = tmp_path / "fixture.py"
    fixture.write_text("no-op", encoding="utf-8")
    with pytest.raises(AttributeError):
        run_probe("does_not_exist", str(fixture), "reported.py")


def test_main_prints_each_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_loader(monkeypatch, _FakeEnforcerModule())
    fixture = tmp_path / "fixture.py"
    fixture.write_text("trigger me", encoding="utf-8")
    exit_code = main(
        ["probe_code_rules_enforcer_check.py", "check_dummy", str(fixture)]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "trigger detected" in captured.out


def test_main_returns_usage_exit_code_when_argv_count_wrong(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["probe_code_rules_enforcer_check.py"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "usage" in captured.err.lower()
