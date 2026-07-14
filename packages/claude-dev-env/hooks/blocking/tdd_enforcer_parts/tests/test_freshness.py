"""Behavioral tests for the freshness parts module."""

import os
import time
from pathlib import Path

from tdd_enforcer_parts import freshness


def test_has_fresh_test_true_for_recent_test_file(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_x(): pass\n")
    assert freshness.has_fresh_test([test_file], freshness._freshness_seconds()) is True


def test_has_fresh_test_false_for_stale_test_file(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_x(): pass\n")
    window = freshness._freshness_seconds()
    stale_timestamp = time.time() - window - 60
    os.utime(test_file, (stale_timestamp, stale_timestamp))
    assert freshness.has_fresh_test([test_file], window) is False


def test_has_fresh_test_false_when_no_test_evidence(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("x = 1\n")
    assert freshness.has_fresh_test([test_file], freshness._freshness_seconds()) is False
