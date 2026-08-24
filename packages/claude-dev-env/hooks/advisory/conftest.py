"""Pytest registration for shared refactor guard test support."""

import sys
from pathlib import Path

advisory_directory = str(Path(__file__).resolve().parent)
if advisory_directory not in sys.path:
    sys.path.insert(0, advisory_directory)

pytest_plugins = ("refactor_guard_test_support",)
