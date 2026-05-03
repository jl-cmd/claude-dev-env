"""Shared field-extraction helpers for GitHub PR review and inline-comment payloads.

The four ``fetch_*_reviews.py`` and ``fetch_*_inline_comments.py`` scripts in
this directory each parse the same JSON shapes and need the same defensive
field-coercion logic for ``user.login``, ``body``, ``submitted_at``, and
``state``. Centralizing the helpers here keeps a single source of truth and
prevents the bug-fix-in-one-copy-only failure mode flagged on PR #337.
"""


def login_of(field_by_key: dict[str, object]) -> str | None:
    """Return the ``user.login`` string from a review/comment payload, or ``None``."""
    user_field = field_by_key.get("user")
    if not isinstance(user_field, dict):
        return None
    login_field = user_field.get("login")
    if not isinstance(login_field, str):
        return None
    return login_field


def body_of(field_by_key: dict[str, object]) -> str:
    """Return the ``body`` string from a review/comment payload, or ``""`` when missing."""
    body_field = field_by_key.get("body")
    if not isinstance(body_field, str):
        return ""
    return body_field


def submitted_at_of(field_by_key: dict[str, object]) -> str:
    """Return the ``submitted_at`` string from a review payload, or ``""`` when missing."""
    submitted_at_field = field_by_key.get("submitted_at")
    if not isinstance(submitted_at_field, str):
        return ""
    return submitted_at_field


def state_of(field_by_key: dict[str, object]) -> str:
    """Return the ``state`` string from a review payload, or ``""`` when missing."""
    state_field = field_by_key.get("state")
    if not isinstance(state_field, str):
        return ""
    return state_field
