"""Resolve whether a reviewer gate is waived, and why, for the convergence check.

::

    flag / env / disk-settings list the reviewer  -> waived, note "copilot_down"
    probe reports the reviewer down                -> waived, "copilot unavailable: <reason>"
    probe reports the reviewer up                   -> enforced, no note
    probe raises                                     -> enforced, "probe error: <exc>" (logged)

Two staleness fixes live here. The disabled decision unions the frozen process
env with the on-disk ``settings.json`` ``CLAUDE_REVIEWS_DISABLED`` list. It logs
any discrepancy between the two. A mid-session settings change then reaches the
flagless mark-ready re-check the hook runs.

An availability probe consults the shared reviewer-availability check. A reviewer
that is out of quota waives its gate with a recorded reason rather than stalling
the run. A caught probe failure fails safe: the gate stays enforced, labelled a
probe error so a broken probe never reads as a healthy enforcement. An uncaught
probe failure propagates and exits the checker non-zero, which the mark-ready
hook also treats as not-ready.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import _pr_converge_path_setup  # noqa: F401
from pr_loop_shared_constants.copilot_quota_constants import (
    COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
)
from pr_loop_shared_constants.reviewer_availability_constants import (
    EXIT_CODE_REVIEWER_DOWN,
)
from pr_loop_shared_constants.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR,
)
from reviewer_availability import evaluate_reviewer_availability

_logger = logging.getLogger(__name__)


class ReviewerWaiver(NamedTuple):
    """Whether a reviewer gate is waived, and the note printed on the bypassed line."""

    is_waived: bool
    bypass_note: str


class _ReviewsDisabled(NamedTuple):
    """The reviews-disabled reviewer tokens seen in the frozen env and on disk."""

    env_tokens: frozenset[str]
    disk_tokens: frozenset[str]


def _settings_json_path() -> Path:
    """Resolve the installed ``settings.json`` from this script's Claude home root."""
    scripts_directory = Path(__file__).resolve().parent
    claude_home = scripts_directory.parent.parent.parent
    return claude_home / "settings.json"


def _tokens_from_text(reviews_disabled_text: str) -> frozenset[str]:
    """Split a CLAUDE_REVIEWS_DISABLED value into its lowercase reviewer tokens."""
    return frozenset(
        each_token.strip().lower()
        for each_token in reviews_disabled_text.split(CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR)
        if each_token.strip()
    )


def _env_disabled_tokens() -> frozenset[str]:
    """Return the reviews-disabled tokens from the frozen process environment."""
    return _tokens_from_text(os.environ.get(CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, ""))


def _disk_disabled_tokens() -> frozenset[str]:
    """Return the reviews-disabled tokens from the on-disk settings.json env block."""
    settings_path = _settings_json_path()
    if not settings_path.is_file():
        return frozenset()
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(settings, dict):
        return frozenset()
    env_block = settings.get("env", {})
    if not isinstance(env_block, dict):
        return frozenset()
    reviews_disabled_text = env_block.get(CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, "")
    if not isinstance(reviews_disabled_text, str):
        return frozenset()
    return _tokens_from_text(reviews_disabled_text)


def _log_settings_discrepancy(reviews: _ReviewsDisabled) -> None:
    """Print a stderr notice when the frozen env and disk settings disagree."""
    _logger.warning(
        "reviewer-availability: %s differs between the frozen env %s and disk settings %s - taking the union.",
        CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
        sorted(reviews.env_tokens),
        sorted(reviews.disk_tokens),
    )


def _is_reviewer_disabled_including_disk(reviewer_token: str) -> bool:
    """Return True when the frozen env or on-disk settings disable the reviewer."""
    reviews = _ReviewsDisabled(_env_disabled_tokens(), _disk_disabled_tokens())
    if reviews.env_tokens != reviews.disk_tokens:
        _log_settings_discrepancy(reviews)
    return reviewer_token in (reviews.env_tokens | reviews.disk_tokens)


@functools.lru_cache(maxsize=None)
def _probe_reviewer_down(reviewer_token: str) -> ReviewerWaiver:
    """Probe reviewer availability once per run; fail safe to enforced on error.

    ::

        exit == reviewer-down  -> ReviewerWaiver(True, "copilot unavailable: <msg>")
        exit == available       -> ReviewerWaiver(False, "")
        probe raises             -> ReviewerWaiver(False, "probe error: <exc>") + stderr

    A caught probe failure keeps the gate enforced rather than silently waiving
    it. It carries a distinct probe-error note so a broken probe never reads as a
    healthy enforcement. ``lru_cache`` runs the underlying check at most once per
    reviewer per process; each gate invocation is a fresh process.
    """
    try:
        availability = evaluate_reviewer_availability(
            reviewer_token=reviewer_token,
            env_file_path=COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as probe_error:
        _logger.warning(
            "reviewer-availability: probe error for %s: %s",
            reviewer_token,
            probe_error,
        )
        return ReviewerWaiver(False, f"probe error: {probe_error}")
    if availability.exit_code == EXIT_CODE_REVIEWER_DOWN:
        return ReviewerWaiver(True, f"{reviewer_token} unavailable: {availability.message}")
    return ReviewerWaiver(False, "")


def _resolve_copilot_waiver(is_copilot_down_flag: bool) -> ReviewerWaiver:
    """Resolve the Copilot waiver from flag, env-and-disk opt-out, then the probe."""
    if is_copilot_down_flag or _is_reviewer_disabled_including_disk(
        CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN
    ):
        return ReviewerWaiver(True, "copilot_down")
    return _probe_reviewer_down(CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN)


def _resolve_bugbot_waiver(is_bugbot_down_flag: bool) -> ReviewerWaiver:
    """Resolve the Bugbot waiver from flag, env-and-disk opt-out, then the probe."""
    if is_bugbot_down_flag or _is_reviewer_disabled_including_disk(
        CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN
    ):
        return ReviewerWaiver(True, "bugbot_down")
    return _probe_reviewer_down(CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN)
