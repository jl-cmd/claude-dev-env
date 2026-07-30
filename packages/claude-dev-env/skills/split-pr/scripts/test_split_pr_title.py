"""Title normalization carries exactly one conventional prefix."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from split_pr_title import normalize_split_title


def test_single_prefix_unchanged() -> None:
    assert normalize_split_title("feat: add gate") == "feat: add gate"


def test_stacked_prefixes_collapse_to_one() -> None:
    assert normalize_split_title("feat: feat: add gate") == "feat: add gate"


def test_bare_title_gets_default_chore_prefix() -> None:
    assert normalize_split_title("add gate") == "chore: add gate"


def test_scoped_prefix_normalized() -> None:
    assert normalize_split_title("fix(hooks): repair gate") == "fix: repair gate"
