"""Specifications for the permission modes the review binary is asked for.

The review binary accepts one permission mode for an ordinary caller and a
different one for root. Naming the wrong mode means the binary refuses the
call, no review runs, and no stamp is ever minted.
"""

from __future__ import annotations

import importlib
import os

import pytest

from dev_env_scripts_constants import code_review_constants


BYPASS_MODE_TOKEN: str = "bypassPermissions"
ACCEPT_EDITS_MODE_TOKEN: str = "acceptEdits"
ROOT_USER_ID: int = 0
UNPRIVILEGED_USER_ID: int = 1000


def _permission_mode_seen_by(
    monkeypatch: pytest.MonkeyPatch, effective_user_id: int
) -> str:
    """Read the review permission mode a caller with this user id resolves."""
    monkeypatch.setattr(os, "geteuid", lambda: effective_user_id)
    reloaded_constants = importlib.reload(code_review_constants)
    return str(reloaded_constants.REVIEW_PERMISSION_MODE)


def test_root_detection_agrees_with_this_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: ROOT_USER_ID)
    reloaded_constants = importlib.reload(code_review_constants)

    assert reloaded_constants.IS_ROOT_CALLER is True
    assert reloaded_constants.ROOT_EFFECTIVE_USER_ID == ROOT_USER_ID


def test_bypass_mode_names_the_token_the_binary_reads() -> None:
    assert code_review_constants.PERMISSION_MODE_BYPASS == BYPASS_MODE_TOKEN


def test_accept_edits_mode_names_the_token_the_binary_reads() -> None:
    assert code_review_constants.PERMISSION_MODE_ACCEPT_EDITS == ACCEPT_EDITS_MODE_TOKEN


def test_a_root_caller_resolves_the_mode_the_binary_accepts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _permission_mode_seen_by(monkeypatch, ROOT_USER_ID) == (
        ACCEPT_EDITS_MODE_TOKEN
    )


def test_an_ordinary_caller_resolves_the_bypass_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _permission_mode_seen_by(monkeypatch, UNPRIVILEGED_USER_ID) == (
        BYPASS_MODE_TOKEN
    )


def test_a_platform_without_a_user_id_still_loads_the_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows exposes no ``os.geteuid``, and the module still imports.

    Reading a missing ``os.geteuid`` raises, and every caller of the review
    invoker dies at import. A platform that reports no user id is never the
    root the review binary refuses, so it reads as an ordinary caller.
    """
    monkeypatch.delattr(os, "geteuid", raising=False)
    reloaded_constants = importlib.reload(code_review_constants)

    assert reloaded_constants.IS_ROOT_CALLER is False
    assert reloaded_constants.REVIEW_PERMISSION_MODE == BYPASS_MODE_TOKEN
