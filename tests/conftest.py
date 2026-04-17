"""Adds .github/scripts to sys.path so sync_ai_rules is importable in tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))
