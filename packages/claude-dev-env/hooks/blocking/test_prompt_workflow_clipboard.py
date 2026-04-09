"""Tests for prompt_workflow_clipboard."""

from __future__ import annotations

import pytest

from prompt_workflow_clipboard import copy_text_to_system_clipboard


def test_empty_text_returns_false() -> None:
    assert copy_text_to_system_clipboard("") is False
    assert copy_text_to_system_clipboard("   \n") is False


def test_respects_skip_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMPT_WORKFLOW_SKIP_CLIPBOARD", "1")
    assert copy_text_to_system_clipboard("hello") is False


@pytest.mark.parametrize(
    "flag_value",
    ("1", "true", "YES", "on"),
)
def test_skip_env_variants(monkeypatch: pytest.MonkeyPatch, flag_value: str) -> None:
    monkeypatch.setenv("PROMPT_WORKFLOW_SKIP_CLIPBOARD", flag_value)
    assert copy_text_to_system_clipboard("payload") is False


def test_prefers_tkinter_when_it_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMPT_WORKFLOW_SKIP_CLIPBOARD", raising=False)
    monkeypatch.setattr(
        "prompt_workflow_clipboard._copy_via_tkinter",
        lambda t: True,
    )

    def _fail_pyperclip(_t: str) -> bool:
        raise AssertionError("pyperclip must run only when tkinter fails")

    monkeypatch.setattr("prompt_workflow_clipboard._copy_via_pyperclip", _fail_pyperclip)
    assert copy_text_to_system_clipboard("hello") is True


def test_falls_back_to_pyperclip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMPT_WORKFLOW_SKIP_CLIPBOARD", raising=False)
    monkeypatch.setattr("prompt_workflow_clipboard._copy_via_tkinter", lambda t: False)
    monkeypatch.setattr("prompt_workflow_clipboard._copy_via_pyperclip", lambda t: True)
    assert copy_text_to_system_clipboard("hello") is True


def test_returns_false_when_both_backends_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMPT_WORKFLOW_SKIP_CLIPBOARD", raising=False)
    monkeypatch.setattr("prompt_workflow_clipboard._copy_via_tkinter", lambda t: False)
    monkeypatch.setattr("prompt_workflow_clipboard._copy_via_pyperclip", lambda t: False)
    assert copy_text_to_system_clipboard("hello") is False
