"""Tests for state_description_blocker_constants.py."""

from __future__ import annotations

import pathlib
import sys

try:
    _HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_HOOKS_ROOT) not in sys.path:
        sys.path.insert(0, str(_HOOKS_ROOT))

    from hooks_constants.state_description_blocker_constants import (
        MULTI_EDIT_NEW_STRING_JOIN_SEPARATOR,
    )
except ImportError as import_error:
    raise ImportError(
        "test_state_description_blocker_constants: cannot import its sibling modules; "
        "ensure the hooks directory is importable."
    ) from import_error


def test_join_separator_is_not_the_empty_string() -> None:
    """A non-empty separator keeps one edit's tail from fusing with the next edit's head.

    An empty separator would let a transition phrase span an edit boundary
    that neither edit's own text carries — see
    test_multi_edit_new_strings_join_on_a_separator_not_concatenation in
    test_state_description_blocker.py for the concrete false-positive case.
    """
    assert MULTI_EDIT_NEW_STRING_JOIN_SEPARATOR != ""
