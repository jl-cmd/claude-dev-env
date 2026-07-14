"""Resolve whether a reviewer gate is waived, and why, for the convergence check.

::

    flag / resolved settings disable the reviewer  -> waived, note "copilot_down"
    copilot out of quota                           -> waived, "copilot unavailable: <reason>"
    bugbot settings-disabled (opt-out / no opt-in) -> waived, "bugbot_down"
    copilot quota available                         -> not waived (live gates run)
    copilot probe error / indeterminate             -> not waived; probe_error_reason set;
                                                       live gates still run (no hard-fail)

When ``~/.claude/settings.json`` is readable it is the sole source for both
``CLAUDE_REVIEWS_DISABLED`` and ``CLAUDE_REVIEWS_ENABLED``. The process env is
the fallback only when that file is missing, unreadable, or not a JSON object.

Bugbot has no quota or outage API. Confirmed-down for Bugbot means the resolved
settings disable it (opt-out or missing opt-in). A runtime Bugbot outage is
detected later as a poll timeout, not at this gate.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import subprocess
from typing import NamedTuple

import _pr_converge_path_setup  # noqa: F401
from copilot_quota import evaluate_copilot_quota
from pr_converge_scripts_constants.convergence_gate_constants import (
    BUGBOT_DOWN_BYPASS_NOTE,
    COPILOT_DOWN_BYPASS_NOTE,
    REVIEWER_UNAVAILABLE_NOTE_TEMPLATE,
    SETTINGS_DISK_FALLBACK_LOG_TEMPLATE,
)
from pr_loop_shared_constants.claude_permissions_constants import (
    get_claude_user_settings_path,
)
from pr_loop_shared_constants.copilot_quota_constants import (
    COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
    EXIT_CODE_OUT_OF_QUOTA,
    EXIT_CODE_QUOTA_AVAILABLE,
)
from pr_loop_shared_constants.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR,
    CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME,
)

_logger = logging.getLogger(__name__)


class ReviewerWaiver(NamedTuple):
    """Whether a reviewer gate is waived, and the note printed on the bypassed line."""

    is_waived: bool
    bypass_note: str
    probe_error_reason: str = ""


class _ReviewsSettings(NamedTuple):
    """Resolved disabled and enabled reviewer tokens for one settings source."""

    disabled_tokens: frozenset[str]
    enabled_tokens: frozenset[str]


def _tokens_from_text(reviews_token_text: str) -> frozenset[str]:
    """Split a comma-separated reviews token list into lowercase tokens."""
    return frozenset(
        each_token.strip().lower()
        for each_token in reviews_token_text.split(CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR)
        if each_token.strip()
    )


def _tokens_from_env(environment_variable_name: str) -> frozenset[str]:
    """Return the tokens listed in a process environment variable."""
    return _tokens_from_text(os.environ.get(environment_variable_name, ""))


def _tokens_from_env_block(
    all_env_entries: dict[str, object], environment_variable_name: str
) -> frozenset[str]:
    """Return the tokens listed under one key of a settings.json env block."""
    reviews_token_text = all_env_entries.get(environment_variable_name, "")
    if not isinstance(reviews_token_text, str):
        return frozenset()
    return _tokens_from_text(reviews_token_text)


def _try_read_disk_env_block() -> dict[str, object] | None:
    """Return the settings.json env block, or None when disk is not authoritative."""
    settings_path = get_claude_user_settings_path()
    if not settings_path.is_file():
        return None
    try:
        settings_payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(settings_payload, dict):
        return None
    all_env_entries = settings_payload.get("env", {})
    if not isinstance(all_env_entries, dict):
        return {}
    return all_env_entries


@functools.lru_cache(maxsize=1)
def _log_disk_settings_fallback_once() -> None:
    """Log once per process that settings.json fell back to the process env."""
    _logger.warning(
        SETTINGS_DISK_FALLBACK_LOG_TEMPLATE,
        CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
        CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME,
    )


def _resolve_reviews_settings() -> _ReviewsSettings:
    """Return disabled and enabled tokens from disk, or env when disk is unreadable."""
    all_disk_env_entries = _try_read_disk_env_block()
    if all_disk_env_entries is not None:
        return _ReviewsSettings(
            disabled_tokens=_tokens_from_env_block(
                all_disk_env_entries, CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME
            ),
            enabled_tokens=_tokens_from_env_block(
                all_disk_env_entries, CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME
            ),
        )
    _log_disk_settings_fallback_once()
    return _ReviewsSettings(
        disabled_tokens=_tokens_from_env(CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME),
        enabled_tokens=_tokens_from_env(CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME),
    )


def _is_copilot_disabled_via_resolved_settings() -> bool:
    """Return True when the resolved settings disable the copilot reviewer."""
    return (
        CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN
        in _resolve_reviews_settings().disabled_tokens
    )


def _is_bugbot_disabled_via_resolved_settings() -> bool:
    """Return True when the resolved settings disable the bugbot reviewer.

    Bugbot is off by default. It is disabled when the disabled list names it, or
    when the enabled list does not name it.
    """
    reviews_settings = _resolve_reviews_settings()
    is_opted_out = (
        CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN in reviews_settings.disabled_tokens
    )
    is_opted_in = CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN in reviews_settings.enabled_tokens
    return is_opted_out or not is_opted_in


def _unavailable_note(reviewer_token: str, message: str) -> str:
    """Format the bypass note for a confirmed-down reviewer."""
    return REVIEWER_UNAVAILABLE_NOTE_TEMPLATE.format(
        token=reviewer_token, message=message
    )


@functools.lru_cache(maxsize=None)
def _probe_copilot_quota() -> ReviewerWaiver:
    """Probe Copilot quota once per run; waive only on confirmed out-of-quota.

    ::

        exit == out-of-quota (1)  -> waived, "copilot unavailable: <msg>"
        exit == available (0)     -> not waived (live gates run)
        exit == API down / no account / other non-zero
                                  -> not waived; probe_error_reason set (live gates run)
        probe raises              -> not waived; probe_error_reason set (live gates run)
    """
    try:
        quota_decision = evaluate_copilot_quota(
            cli_account=None,
            env_file_path=COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as probe_error:
        _logger.warning(
            "reviewer-availability: probe error for %s: %s",
            CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
            probe_error,
        )
        return ReviewerWaiver(False, "", str(probe_error))
    if quota_decision.exit_code == EXIT_CODE_OUT_OF_QUOTA:
        return ReviewerWaiver(
            True,
            _unavailable_note(
                CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN, quota_decision.message
            ),
            "",
        )
    if quota_decision.exit_code == EXIT_CODE_QUOTA_AVAILABLE:
        return ReviewerWaiver(False, "", "")
    return ReviewerWaiver(False, "", quota_decision.message)


def _waiver_from_cli_flag(is_down_flag: bool, bypass_note: str) -> ReviewerWaiver:
    """Build a waiver from an explicit CLI flag alone (fixture offline path)."""
    if is_down_flag:
        return ReviewerWaiver(True, bypass_note, "")
    return ReviewerWaiver(False, "", "")


def _resolve_copilot_waiver(is_copilot_down_flag: bool) -> ReviewerWaiver:
    """Resolve the Copilot waiver from flag, resolved settings, then the quota probe."""
    if is_copilot_down_flag or _is_copilot_disabled_via_resolved_settings():
        return ReviewerWaiver(True, COPILOT_DOWN_BYPASS_NOTE, "")
    return _probe_copilot_quota()


def _resolve_bugbot_waiver(is_bugbot_down_flag: bool) -> ReviewerWaiver:
    """Resolve the Bugbot waiver from flag, then resolved settings.

    Bugbot has no quota or outage API. Once the resolved settings (disk when
    readable, else env) confirm the opt-in, the gate is enforced. Re-probing
    via ``evaluate_reviewer_availability`` would re-read the process env and
    undo a mid-session disk enable of Bugbot.
    """
    if is_bugbot_down_flag or _is_bugbot_disabled_via_resolved_settings():
        return ReviewerWaiver(True, BUGBOT_DOWN_BYPASS_NOTE, "")
    return ReviewerWaiver(False, "", "")
