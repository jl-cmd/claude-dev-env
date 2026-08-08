"""Tests for the disabled hook_log_stop_wrapper Stop hook."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from diagnostic import hook_log_stop_wrapper


def test_main_returns_zero_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled main exits success and never launches the extractor."""

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Popen must not run while the wrapper is disabled")

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _raise)

    assert hook_log_stop_wrapper.main() == 0


def test_main_does_not_write_debounce_timestamp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Disabled main leaves the debounce timestamp file untouched."""
    timestamp_file = tmp_path / "stop_wrapper_last_run.txt"
    monkeypatch.setattr(
        hook_log_stop_wrapper,
        "_last_run_timestamp_path",
        lambda: timestamp_file,
    )
    monkeypatch.setattr(
        hook_log_stop_wrapper.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Popen must not run while the wrapper is disabled")
        ),
    )

    assert hook_log_stop_wrapper.main() == 0
    assert not timestamp_file.exists()
