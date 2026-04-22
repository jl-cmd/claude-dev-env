"""Tests for DynamicStderrHandler — resolves sys.stderr at emit time."""

from __future__ import annotations

import logging
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config.dynamic_stderr_handler import DynamicStderrHandler


def _make_logger_with_handler() -> tuple[logging.Logger, DynamicStderrHandler]:
    handler_instance = DynamicStderrHandler()
    handler_instance.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    test_logger = logging.getLogger("test_dynamic_stderr_handler_logger")
    for each_existing_handler in list(test_logger.handlers):
        test_logger.removeHandler(each_existing_handler)
    test_logger.addHandler(handler_instance)
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False
    return test_logger, handler_instance


def test_emit_writes_to_current_sys_stderr() -> None:
    test_logger, _ = _make_logger_with_handler()
    captured_stderr = StringIO()
    with patch("sys.stderr", captured_stderr):
        test_logger.error("hello from handler")
    assert "hello from handler" in captured_stderr.getvalue()


def test_emit_resolves_stderr_at_emit_time_not_construction_time() -> None:
    test_logger, _ = _make_logger_with_handler()
    first_captured_stderr = StringIO()
    second_captured_stderr = StringIO()
    with patch("sys.stderr", first_captured_stderr):
        test_logger.error("first message")
    with patch("sys.stderr", second_captured_stderr):
        test_logger.error("second message")
    assert "first message" in first_captured_stderr.getvalue()
    assert "second message" in second_captured_stderr.getvalue()
    assert "second message" not in first_captured_stderr.getvalue()
