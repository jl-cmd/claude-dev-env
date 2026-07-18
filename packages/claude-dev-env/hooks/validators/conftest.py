"""Pytest fixture module ensuring validators directory is importable regardless of invocation cwd."""

import sys
from pathlib import Path


VALIDATORS_DIRECTORY = Path(__file__).resolve().parent
HOOKS_DIRECTORY = VALIDATORS_DIRECTORY.parent

if str(VALIDATORS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIRECTORY))

if str(HOOKS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIRECTORY))
