"""Behavior tests for the code_rules_shared code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_enforcer import (  # noqa: E402
    prior_and_post_edit_content,
)
from code_rules_shared import (  # noqa: E402
    changed_line_numbers,
)

code_rules_enforcer = SimpleNamespace(
    changed_line_numbers=changed_line_numbers,
    prior_and_post_edit_content=prior_and_post_edit_content,
)


def test_readable_prior_yields_consistent_prior_and_reconstruction(tmp_path) -> None:
    """When the prior reads cleanly, the helper returns the same prior content it
    reconstructed the post-edit view from, so the two never diverge across two
    independent reads."""
    source_file = tmp_path / "module.py"
    original = "alpha = 1\nbeta = 2\n"
    source_file.write_text(original, encoding="utf-8")
    prior_content, post_edit_content = code_rules_enforcer.prior_and_post_edit_content(
        str(source_file),
        old_string="beta = 2\n",
        new_string="beta = 3\n",
    )
    assert prior_content == original
    assert post_edit_content == "alpha = 1\nbeta = 3\n"
    changed = code_rules_enforcer.changed_line_numbers(prior_content, post_edit_content)
    assert changed == {2}
