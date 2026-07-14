"""Verify every convergence pre-condition for a PR before marking it ready.

::

    check_convergence.py --owner O --repo R --pr-number N [flags]
        exit 0  ok:   every gate passed — safe to mark ready
        exit 1  flag: a gate failed (FAIL lines print to stdout)
        exit 2  flag: gh CLI error

    check_convergence.py --owner O --repo R --pr-number N --fixture PATH [flags]
        Same stdout and exit codes as the live path, reading a frozen GitHub
        API snapshot from PATH instead of calling ``gh`` against current state.

Each bypass flag closes one reviewer gate when that reviewer is unavailable.
``--bugbot-down`` skips the bugbot check-run gate. ``--copilot-down`` skips
the Copilot review and pending-review gates. ``--bugteam-post-blocked`` skips
the bugteam CLEAN-review gate. ``--codex-down`` skips the Codex review gate.

Each flag also honors its own reviews-disabled token: "bugbot", "copilot",
"bugteam", or "codex". A caller that cannot pass the flag reaches the same
bypass by exporting the token. The mark-ready blocker hook re-runs this script
with no flags, so its convergence re-check reads the bypass from the exported
token instead. For Codex, sticky job-dir state ``codex_down: true`` is a third
bypass source when the original run could not re-pass ``--codex-down``.

Copilot and Bugbot waivers are disk-authoritative.
When ``~/.claude/settings.json`` is readable, its env block is the single source.
The frozen process env is only a fallback when that disk read fails (logged once).
Bugteam's opt-out is env-only via ``_resolve_bugteam_post_blocked``.
A probe error does not waive the gate; the live GitHub checks still run.

The Codex gate is conditional-required: it demands
``codex_clean_at == current_head`` only when the weekly usage probe reports
more than the probe's threshold percent left. At or below that threshold, null
usage, the codex token, or ``codex_down`` never blocks ready.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import _pr_converge_path_setup  # noqa: F401
from check_convergence_gates import (
    _check_bot_review,
    _check_bugbot,
    _check_bugbot_not_dirty,
    _flatten_paginated_reviews,
    _get_mergeable,
    _get_pr_head_sha,
    _gh_api_paginated,
    _short_sha,
    _sort_reviews_newest_first,
    _evaluate_mergeable_from_pr_object,
)
from check_convergence_thread_gates import (
    _check_no_pending_reviews,
    _count_unresolved_bot_threads,
)
from codex_review_scripts_constants.codex_usage_probe_constants import (
    USAGE_REPORT_KEY_PERCENT_LEFT,
)
from codex_usage_probe import is_codex_review_required, probe_weekly_usage_via_subprocess
from pr_converge_scripts_constants.convergence_gate_constants import (
    BUGBOT_DOWN_BYPASS_NOTE,
    CLAUDE_JOB_DIR_ENV_VAR_NAME,
    CODEX_BYPASS_DETAIL,
    CODEX_CLEAN_AT_STATE_KEY,
    CODEX_CLEAN_DETAIL_TEMPLATE,
    CODEX_DOWN_STATE_KEY,
    CODEX_GATE_LABEL,
    CODEX_MISSING_CLEAN_DETAIL_TEMPLATE,
    CODEX_SKIPPED_USAGE_DETAIL,
    COPILOT_DOWN_BYPASS_NOTE,
    FIXTURE_DEFAULT_PENDING_DETAIL,
    FIXTURE_DEFAULT_THREADS_DETAIL,
    FIXTURE_KEY_CODEX_CLEAN_AT,
    FIXTURE_KEY_CODEX_PERCENT_LEFT,
    FIXTURE_KEY_HEAD_SHA,
    FIXTURE_KEY_PENDING_REVIEWS_DETAIL,
    FIXTURE_KEY_PENDING_REVIEWS_PASSED,
    FIXTURE_KEY_PR_OBJECT,
    FIXTURE_KEY_REVIEWS,
    FIXTURE_KEY_UNRESOLVED_BOT_THREADS_DETAIL,
    FIXTURE_KEY_UNRESOLVED_BOT_THREADS_PASSED,
    MINIMUM_ABBREVIATED_SHA_LENGTH,
    PR_CONVERGE_STATE_FILENAME,
)
from pr_converge_skill_constants.constants import (
    ALL_COPILOT_CLEAN_REVIEW_STATES,
    ALL_COPILOT_DIRTY_REVIEW_STATES,
    BUGTEAM_LEGACY_CLEAN_TOKEN,
    BUGTEAM_LEGACY_HEADER_PREFIX,
    BUGTEAM_NEW_CLEAN_LABEL,
    BUGTEAM_NEW_HEADER_PREFIX,
    COPILOT_LOGIN_FILTER_SUBSTRING,
    GH_REVIEWS_PATH_TEMPLATE,
    REVIEWS_PER_PAGE,
)
from reviews_disabled import (
    is_bugbot_disabled_via_env,
    is_bugteam_disabled_via_env,
    is_codex_disabled_via_env,
    is_copilot_disabled_via_env,
)
from check_convergence_availability import (
    _resolve_bugbot_waiver,
    _resolve_copilot_waiver,
    _waiver_from_cli_flag,
)

JsonObject = dict[str, object]
GateCondition = tuple[str, tuple[bool, str]]


class ConvergenceFixture(NamedTuple):
    """Frozen GitHub API snapshot one fixture gate run evaluates."""

    head_sha: str
    pr_object: JsonObject
    reviews: list[JsonObject]
    is_zero_unresolved_bot_threads: bool
    unresolved_bot_threads_detail: str
    is_no_pending_reviews: bool
    pending_reviews_detail: str
    codex_percent_left: float | None
    codex_clean_at: str | None


class GateContext(NamedTuple):
    """The PR coordinates and per-reviewer bypass flags one gate run evaluates."""

    owner: str
    repo: str
    number: int
    head_sha: str
    is_bugbot_down: bool
    is_copilot_down: bool
    is_bugteam_post_blocked: bool
    is_codex_down: bool
    bugbot_bypass_note: str = BUGBOT_DOWN_BYPASS_NOTE
    copilot_bypass_note: str = COPILOT_DOWN_BYPASS_NOTE
    live_codex_clean_at: str | None = None
    fixture: ConvergenceFixture | None = None


def _is_bugteam_review(review_body: str) -> bool:
    """Return True when a review body opens with a bugteam audit header prefix."""
    return review_body.startswith(BUGTEAM_NEW_HEADER_PREFIX) or review_body.startswith(
        BUGTEAM_LEGACY_HEADER_PREFIX
    )


def _is_clean_bugteam_review(review_body: str) -> bool:
    """Return True when a bugteam audit review body declares a clean pass."""
    if review_body.startswith(BUGTEAM_NEW_HEADER_PREFIX):
        first_line = review_body.splitlines()[0]
        return BUGTEAM_NEW_CLEAN_LABEL in first_line
    if review_body.startswith(BUGTEAM_LEGACY_HEADER_PREFIX):
        return review_body.rstrip().endswith(BUGTEAM_LEGACY_CLEAN_TOKEN)
    return False


def _bugteam_review_detail(review: JsonObject, head_sha: str) -> tuple[bool, str] | None:
    """Return the pass flag and detail for a bugteam review on HEAD, or None."""
    body = review.get("body", "")
    if not isinstance(body, str) or not _is_bugteam_review(body):
        return None
    commit_id = review.get("commit_id", "")
    if not isinstance(commit_id, str) or not commit_id.startswith(head_sha):
        return None
    review_id = review.get("id", "?")
    short_commit = _short_sha(commit_id)
    if _is_clean_bugteam_review(body):
        return True, f"review {review_id}, clean bugteam audit, commit {short_commit}"
    return False, f"review {review_id}, dirty bugteam audit, commit {short_commit}"


def _evaluate_bugteam_clean_from_reviews(
    all_reviews: list[JsonObject], head_sha: str
) -> tuple[bool, str]:
    """Return whether the newest bugteam audit on HEAD is clean (pure, no network).

    Args:
        all_reviews: Review objects newest-first as returned by the GitHub reviews API.
        head_sha: Current PR HEAD commit SHA.

    Returns:
        (passed, detail) for the first bugteam review on HEAD, or a missing-review failure.
    """
    for each_review in all_reviews:
        detail = _bugteam_review_detail(each_review, head_sha)
        if detail is not None:
            return detail
    return False, f"no bugteam review found on {_short_sha(head_sha)}"


def _check_bugteam_clean(*, owner: str, repo: str, number: int, head_sha: str) -> tuple[bool, str]:
    """Return whether the newest bugteam audit review on HEAD declares a clean pass."""
    endpoint = GH_REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api_paginated(f"{endpoint}?per_page={REVIEWS_PER_PAGE}")
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    all_flat = _flatten_paginated_reviews(stdout)
    if all_flat is None:
        return False, "unexpected gh api response shape (expected list)"
    return _evaluate_bugteam_clean_from_reviews(all_flat, head_sha)


def _bypassed_note(bypass_note: str) -> str:
    """Format the PASS detail line for a gate bypassed for the given reason."""
    return f"bypassed ({bypass_note})"


def _bugbot_conditions(context: GateContext) -> list[GateCondition]:
    """Build the Bugbot gate conditions, bypassed when Bugbot is down."""
    if context.is_bugbot_down:
        return [
            (
                "bugbot_clean_at == current_head",
                (True, _bypassed_note(context.bugbot_bypass_note)),
            )
        ]
    if context.fixture is not None:
        return [
            (
                "bugbot_clean_at == current_head",
                (False, "fixture has no bugbot check-runs; pass --bugbot-down"),
            )
        ]
    conditions: list[GateCondition] = [
        (
            "bugbot_clean_at == current_head",
            _check_bugbot(owner=context.owner, repo=context.repo, sha=context.head_sha),
        )
    ]
    if conditions[-1][1][0]:
        conditions.append(
            (
                "bugbot review body clean",
                _check_bugbot_not_dirty(
                    owner=context.owner,
                    repo=context.repo,
                    number=context.number,
                    head_sha=context.head_sha,
                ),
            )
        )
    return conditions


def _bugteam_condition(context: GateContext) -> GateCondition:
    """Build the bugteam CLEAN-review condition, skipped when the post was blocked."""
    if context.is_bugteam_post_blocked:
        return ("bugteam_clean_at == current_head", (True, "bypassed (bugteam_post_blocked)"))
    if context.fixture is not None:
        return (
            "bugteam_clean_at == current_head",
            _evaluate_bugteam_clean_from_reviews(context.fixture.reviews, context.head_sha),
        )
    return (
        "bugteam_clean_at == current_head",
        _check_bugteam_clean(
            owner=context.owner,
            repo=context.repo,
            number=context.number,
            head_sha=context.head_sha,
        ),
    )


def _copilot_review_condition(context: GateContext) -> GateCondition:
    """Build the Copilot review gate condition, bypassed when Copilot is down."""
    if context.is_copilot_down:
        return (
            "copilot_clean_at == current_head",
            (True, _bypassed_note(context.copilot_bypass_note)),
        )
    if context.fixture is not None:
        return (
            "copilot_clean_at == current_head",
            (False, "fixture has no copilot review; pass --copilot-down"),
        )
    return (
        "copilot_clean_at == current_head",
        _check_bot_review(
            owner=context.owner,
            repo=context.repo,
            number=context.number,
            head_sha=context.head_sha,
            login_substring=COPILOT_LOGIN_FILTER_SUBSTRING,
            clean_states=ALL_COPILOT_CLEAN_REVIEW_STATES,
            dirty_states=ALL_COPILOT_DIRTY_REVIEW_STATES,
            label="copilot",
        ),
    )


def _sha_matches_head(stamp_sha: str, head_sha: str) -> bool:
    """Return True when a clean-at stamp matches the PR HEAD SHA (full or prefix).

    ::

        stamp 86454e3d..., head 86454e3d...  -> True  (full match)
        stamp 86454e3,    head 86454e3d...   -> True  (abbreviated stamp)
        stamp 8,          head 86454e3d...   -> False (below the abbreviation floor)

    A prefix shorter than an abbreviated SHA matches many commits, so a stamp
    that short never passes the gate.

    Args:
        stamp_sha: The ``codex_clean_at`` stamp under test.
        head_sha: Current PR HEAD commit SHA.

    Returns:
        True when the two name the same commit.
    """
    if len(stamp_sha) < MINIMUM_ABBREVIATED_SHA_LENGTH:
        return False
    if len(head_sha) < MINIMUM_ABBREVIATED_SHA_LENGTH:
        return False
    lowered_stamp_sha = stamp_sha.lower()
    lowered_head_sha = head_sha.lower()
    return lowered_head_sha.startswith(lowered_stamp_sha) or lowered_stamp_sha.startswith(
        lowered_head_sha
    )


def _evaluate_codex_clean(
    *,
    read_percent_left: Callable[[], float | None],
    codex_clean_at: str | None,
    head_sha: str,
) -> tuple[bool, str]:
    """Return whether the conditional Codex gate passes for the given stamp and usage.

    ::

        clean stamp on head                -> pass  (usage never read)
        no stamp, percent None or <= limit -> skip  (never blocks)
        no stamp, percent > limit          -> fail

    A stamp on the current HEAD settles the gate on its own, so the usage read
    stays behind it: the weekly probe spawns a Codex subprocess, and the common
    already-clean tick has no reason to pay for one.

    Args:
        read_percent_left: Reads weekly Codex percent remaining, or None when unknown.
        codex_clean_at: HEAD SHA where Codex last reported clean, or None.
        head_sha: Current PR HEAD commit SHA.

    Returns:
        (passed, detail) for the Codex gate condition line.
    """
    if codex_clean_at is not None and _sha_matches_head(codex_clean_at, head_sha):
        return True, CODEX_CLEAN_DETAIL_TEMPLATE % _short_sha(head_sha)
    if not is_codex_review_required(read_percent_left()):
        return True, CODEX_SKIPPED_USAGE_DETAIL
    return False, CODEX_MISSING_CLEAN_DETAIL_TEMPLATE % _short_sha(head_sha)


def _probe_codex_percent_left() -> float | None:
    """Probe weekly Codex usage and return percent remaining, or None when unknown."""
    try:
        usage_report = probe_weekly_usage_via_subprocess()
    except (
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
    ):
        return None
    raw_percent = usage_report.get(USAGE_REPORT_KEY_PERCENT_LEFT)
    if isinstance(raw_percent, bool):
        return None
    if isinstance(raw_percent, (int, float)):
        return float(raw_percent)
    return None


def _read_job_state() -> dict[str, object]:
    """Read the single-PR job-dir state file, or an empty mapping when unreadable.

    ::

        CLAUDE_JOB_DIR unset      -> {}
        state file absent         -> {}
        corrupt or non-object     -> {}
        {"codex_down": true}      -> {"codex_down": True}

    Args:
        None.

    Returns:
        The parsed state object, or an empty dict when no state is readable.
    """
    job_directory = os.environ.get(CLAUDE_JOB_DIR_ENV_VAR_NAME)
    if not job_directory:
        return {}
    state_path = Path(job_directory) / PR_CONVERGE_STATE_FILENAME
    if not state_path.is_file():
        return {}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _read_codex_clean_at_from_job_state(all_job_state_fields: dict[str, object]) -> str | None:
    """Read ``codex_clean_at`` from an already-read job-dir state mapping."""
    clean_at = all_job_state_fields.get(CODEX_CLEAN_AT_STATE_KEY)
    if isinstance(clean_at, str) and clean_at:
        return clean_at
    return None


def _read_codex_down_from_job_state(all_job_state_fields: dict[str, object]) -> bool:
    """Return True when job-dir state records sticky ``codex_down`` as JSON true.

    ::

        {"codex_down": true}   -> True
        {"codex_down": false}  -> False
        missing key / corrupt  -> False

    Only exact boolean true counts; strings, numbers, and missing values do not.

    Args:
        all_job_state_fields: Parsed job-dir state, empty when none is readable.

    Returns:
        True when the state records ``codex_down`` as JSON true.
    """
    return all_job_state_fields.get(CODEX_DOWN_STATE_KEY) is True


def _resolve_live_codex_clean_at(
    cli_codex_clean_at: str | None, all_job_state_fields: dict[str, object]
) -> str | None:
    """Prefer the CLI stamp, then the job-dir state stamp, for the live Codex gate.

    Args:
        cli_codex_clean_at: Stamp passed through ``--codex-clean-at``, or None.
        all_job_state_fields: Parsed job-dir state, empty when none is readable.

    Returns:
        The stamp the live Codex gate checks against HEAD, or None.
    """
    if cli_codex_clean_at:
        return cli_codex_clean_at
    return _read_codex_clean_at_from_job_state(all_job_state_fields)


def _codex_condition(context: GateContext) -> GateCondition:
    """Build the conditional Codex gate, bypassed when Codex is down."""
    if context.is_codex_down:
        return (CODEX_GATE_LABEL, (True, CODEX_BYPASS_DETAIL))
    if context.fixture is not None:
        fixture_percent_left = context.fixture.codex_percent_left
        return (
            CODEX_GATE_LABEL,
            _evaluate_codex_clean(
                read_percent_left=lambda: fixture_percent_left,
                codex_clean_at=context.fixture.codex_clean_at,
                head_sha=context.head_sha,
            ),
        )
    return (
        CODEX_GATE_LABEL,
        _evaluate_codex_clean(
            read_percent_left=_probe_codex_percent_left,
            codex_clean_at=context.live_codex_clean_at,
            head_sha=context.head_sha,
        ),
    )


def _pending_reviews_condition(context: GateContext) -> GateCondition:
    """Build the pending-requested-reviews condition, bypassed when Copilot is down."""
    if context.is_copilot_down:
        return (
            "no pending requested reviews",
            (True, _bypassed_note(context.copilot_bypass_note)),
        )
    if context.fixture is not None:
        return (
            "no pending requested reviews",
            (
                context.fixture.is_no_pending_reviews,
                context.fixture.pending_reviews_detail,
            ),
        )
    return (
        "no pending requested reviews",
        _check_no_pending_reviews(owner=context.owner, repo=context.repo, number=context.number),
    )


def _mergeable_condition(context: GateContext) -> GateCondition:
    """Build the mergeable condition from live gh or the frozen fixture PR object."""
    if context.fixture is not None:
        return (
            "PR is mergeable",
            _evaluate_mergeable_from_pr_object(context.fixture.pr_object),
        )
    return (
        "PR is mergeable",
        _get_mergeable(owner=context.owner, repo=context.repo, number=context.number),
    )


def _threads_condition(context: GateContext) -> GateCondition:
    """Build the unresolved-bot-threads condition from live gh or the fixture."""
    if context.fixture is not None:
        return (
            "zero unresolved bot threads",
            (
                context.fixture.is_zero_unresolved_bot_threads,
                context.fixture.unresolved_bot_threads_detail,
            ),
        )
    return (
        "zero unresolved bot threads",
        _count_unresolved_bot_threads(
            owner=context.owner, repo=context.repo, number=context.number
        ),
    )


def _state_conditions(context: GateContext) -> list[GateCondition]:
    """Build the thread, mergeable, and pending-review conditions in gate order."""
    return [
        _threads_condition(context),
        _mergeable_condition(context),
        _pending_reviews_condition(context),
    ]


def _build_all_conditions(context: GateContext) -> list[GateCondition]:
    """Build the ordered convergence conditions the checker prints and grades."""
    conditions = list(_bugbot_conditions(context))
    conditions.append(_bugteam_condition(context))
    conditions.append(_copilot_review_condition(context))
    conditions.append(_codex_condition(context))
    conditions.extend(_state_conditions(context))
    return conditions


def _print_conditions(all_conditions: list[GateCondition]) -> int:
    """Write one PASS/FAIL line per condition and return the aggregate exit code."""
    is_all_passed = True
    for each_index, (each_label, (each_passed, each_detail)) in enumerate(all_conditions, start=1):
        status = "PASS" if each_passed else "FAIL"
        sys.stdout.write(f"{each_index}. {each_label}: {status} — {each_detail}\n")
        if not each_passed:
            is_all_passed = False
    sys.stdout.write("\n")
    if is_all_passed:
        sys.stdout.write("All pre-conditions met — PR is ready to mark ready.\n")
    else:
        sys.stdout.write("One or more pre-conditions not met — do not mark ready.\n")
    return 0 if is_all_passed else 1


def _evaluate_convergence(context: GateContext) -> int:
    """Write the HEAD line then the per-condition PASS/FAIL lines for a gate run."""
    sys.stdout.write(f"HEAD: {_short_sha(context.head_sha)}\n\n")
    return _print_conditions(_build_all_conditions(context))


def _load_convergence_fixture(from_path: Path) -> ConvergenceFixture:
    """Load a frozen GitHub API snapshot from JSON for fixture replay.

    Args:
        from_path: Path to a JSON fixture file.

    Returns:
        ConvergenceFixture with head, reviews, mergeable PR object, and thread/pending facts.

    Raises:
        ValueError: When required keys are missing or mistyped.
    """
    payload = json.loads(from_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture root must be a JSON object")
    head_sha = payload.get(FIXTURE_KEY_HEAD_SHA)
    pr_object = payload.get(FIXTURE_KEY_PR_OBJECT)
    reviews = payload.get(FIXTURE_KEY_REVIEWS)
    if not isinstance(head_sha, str) or not head_sha:
        raise ValueError("fixture head_sha must be a non-empty string")
    if not isinstance(pr_object, dict):
        raise ValueError("fixture pr_object must be an object")
    if not isinstance(reviews, list):
        raise ValueError("fixture reviews must be a list")
    typed_reviews = _sort_reviews_newest_first(
        [each for each in reviews if isinstance(each, dict)]
    )
    is_threads_ok = payload.get(FIXTURE_KEY_UNRESOLVED_BOT_THREADS_PASSED)
    threads_detail = payload.get(
        FIXTURE_KEY_UNRESOLVED_BOT_THREADS_DETAIL, FIXTURE_DEFAULT_THREADS_DETAIL
    )
    is_pending_ok = payload.get(FIXTURE_KEY_PENDING_REVIEWS_PASSED)
    pending_detail = payload.get(
        FIXTURE_KEY_PENDING_REVIEWS_DETAIL, FIXTURE_DEFAULT_PENDING_DETAIL
    )
    if not isinstance(is_threads_ok, bool):
        raise ValueError("fixture unresolved_bot_threads_passed must be a bool")
    if not isinstance(threads_detail, str):
        raise ValueError("fixture unresolved_bot_threads_detail must be a string")
    if not isinstance(is_pending_ok, bool):
        raise ValueError("fixture pending_reviews_passed must be a bool")
    if not isinstance(pending_detail, str):
        raise ValueError("fixture pending_reviews_detail must be a string")
    codex_percent_left = payload.get(FIXTURE_KEY_CODEX_PERCENT_LEFT)
    codex_clean_at = payload.get(FIXTURE_KEY_CODEX_CLEAN_AT)
    if isinstance(codex_percent_left, bool):
        raise ValueError("fixture codex_percent_left must be a number or null")
    if codex_percent_left is not None and not isinstance(codex_percent_left, (int, float)):
        raise ValueError("fixture codex_percent_left must be a number or null")
    if codex_clean_at is not None and not isinstance(codex_clean_at, str):
        raise ValueError("fixture codex_clean_at must be a string or null")
    typed_percent_left: float | None = (
        float(codex_percent_left) if isinstance(codex_percent_left, (int, float)) else None
    )
    typed_codex_clean_at: str | None = codex_clean_at if isinstance(codex_clean_at, str) else None
    return ConvergenceFixture(
        head_sha=head_sha,
        pr_object=pr_object,
        reviews=typed_reviews,
        is_zero_unresolved_bot_threads=is_threads_ok,
        unresolved_bot_threads_detail=threads_detail,
        is_no_pending_reviews=is_pending_ok,
        pending_reviews_detail=pending_detail,
        codex_percent_left=typed_percent_left,
        codex_clean_at=typed_codex_clean_at,
    )


def check_all(
    owner: str,
    repo: str,
    number: int,
    is_bugbot_down: bool,
    is_copilot_down: bool,
    is_bugteam_post_blocked: bool,
    is_codex_down: bool,
    live_codex_clean_at: str | None,
    bugbot_bypass_note: str = BUGBOT_DOWN_BYPASS_NOTE,
    copilot_bypass_note: str = COPILOT_DOWN_BYPASS_NOTE,
) -> int:
    """Run every convergence gate and print one PASS/FAIL line per condition.

    Args:
        owner: GitHub repository owner login.
        repo: GitHub repository name.
        number: Pull request number to inspect.
        is_bugbot_down: True bypasses the bugbot check-run and review-body gates.
        is_copilot_down: True bypasses the Copilot review and pending gates.
        is_bugteam_post_blocked: True skips the bugteam CLEAN-review gate.
        is_codex_down: True bypasses the conditional Codex review gate.
        live_codex_clean_at: Optional SHA stamp for the live Codex clean-at check.
        bugbot_bypass_note: Detail note printed when the bugbot gate is bypassed.
        copilot_bypass_note: Detail note printed when the Copilot gates are bypassed.

    Returns:
        0 when every gate passes, 1 when at least one gate fails.
    """
    head_sha = _get_pr_head_sha(owner=owner, repo=repo, number=number)
    context = GateContext(
        owner=owner,
        repo=repo,
        number=number,
        head_sha=head_sha,
        is_bugbot_down=is_bugbot_down,
        is_copilot_down=is_copilot_down,
        is_bugteam_post_blocked=is_bugteam_post_blocked,
        is_codex_down=is_codex_down,
        bugbot_bypass_note=bugbot_bypass_note,
        copilot_bypass_note=copilot_bypass_note,
        live_codex_clean_at=live_codex_clean_at,
        fixture=None,
    )
    return _evaluate_convergence(context)


def _check_all_from_fixture(
    owner: str,
    repo: str,
    number: int,
    fixture: ConvergenceFixture,
    is_bugbot_down: bool,
    is_copilot_down: bool,
    is_bugteam_post_blocked: bool,
    is_codex_down: bool,
    bugbot_bypass_note: str = BUGBOT_DOWN_BYPASS_NOTE,
    copilot_bypass_note: str = COPILOT_DOWN_BYPASS_NOTE,
) -> int:
    """Run every convergence gate against a frozen API snapshot.

    Args:
        owner: GitHub repository owner login.
        repo: GitHub repository name.
        number: Pull request number recorded in the snapshot.
        fixture: Frozen GitHub API snapshot (no live `gh` calls).
        is_bugbot_down: True bypasses the bugbot check-run and review-body gates.
        is_copilot_down: True bypasses the Copilot review and pending gates.
        is_bugteam_post_blocked: True skips the bugteam CLEAN-review gate.
        is_codex_down: True bypasses the conditional Codex review gate.
        bugbot_bypass_note: Detail note printed when the bugbot gate is bypassed.
        copilot_bypass_note: Detail note printed when the Copilot gates are bypassed.

    Returns:
        0 when every gate passes, 1 when at least one gate fails.
    """
    context = GateContext(
        owner=owner,
        repo=repo,
        number=number,
        head_sha=fixture.head_sha,
        is_bugbot_down=is_bugbot_down,
        is_copilot_down=is_copilot_down,
        is_bugteam_post_blocked=is_bugteam_post_blocked,
        is_codex_down=is_codex_down,
        bugbot_bypass_note=bugbot_bypass_note,
        copilot_bypass_note=copilot_bypass_note,
        live_codex_clean_at=None,
        fixture=fixture,
    )
    return _evaluate_convergence(context)


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the convergence checker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--pr-number", required=True, type=int, help="Pull request number")
    parser.add_argument(
        "--fixture",
        default=None,
        help="Path to a frozen GitHub API JSON snapshot for offline replay.",
    )
    parser.add_argument(
        "--bugbot-down",
        action="store_true",
        help="Bypass the bugbot check-run gate when Cursor Bugbot is unreachable on HEAD.",
    )
    parser.add_argument(
        "--copilot-down",
        action="store_true",
        help="Bypass the Copilot review and pending-review gates when Copilot is down on HEAD.",
    )
    parser.add_argument(
        "--bugteam-post-blocked",
        action="store_true",
        help="Skip the bugteam CLEAN-review gate when the environment refused the CLEAN post on HEAD.",
    )
    parser.add_argument(
        "--codex-down",
        action="store_true",
        help="Bypass the conditional Codex review gate when Codex is down or opted out.",
    )
    parser.add_argument(
        "--codex-clean-at",
        default=None,
        help="HEAD SHA where Codex last reported clean (live path; optional when job-dir state holds it).",
    )
    return parser


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the convergence checker.

    Args:
        all_argv: Argument list excluding the program name.

    Returns:
        Namespace exposing owner, repo, pr_number, fixture, bugbot_down, copilot_down,
        bugteam_post_blocked, codex_down, and codex_clean_at attributes.
    """
    return _build_argument_parser().parse_args(all_argv)


def _resolve_bugbot_down(is_bugbot_down_flag: bool) -> bool:
    """Pinned contract/unit-test helper for the bugbot flag and env bypass.

    Production ``main()`` resolves Bugbot waivers through ``_resolve_bugbot_waiver``.
    This function serves only pinned contract and unit tests; issue #120 tracks
    its removal.
    """
    return is_bugbot_down_flag or is_bugbot_disabled_via_env()


def _resolve_copilot_down(is_copilot_down_flag: bool) -> bool:
    """Pinned contract/unit-test helper for the copilot flag and env bypass.

    Production ``main()`` resolves Copilot waivers through ``_resolve_copilot_waiver``.
    This function serves only pinned contract and unit tests; issue #120 tracks
    its removal.
    """
    return is_copilot_down_flag or is_copilot_disabled_via_env()


def _resolve_bugteam_post_blocked(is_bugteam_post_blocked_flag: bool) -> bool:
    """Combine the --bugteam-post-blocked flag with the bugteam env opt-out.

    ::

        flag True, env unset                        -> True   (caller passed the flag)
        flag False, reviews-disabled lists bugteam  -> True   (exported token)
        flag False, env unset                       -> False  (gate runs)

    The mark-ready blocker hook re-runs this script with no flags, so the env
    fallback lets an exported bugteam token carry the bypass into that re-check.
    """
    return is_bugteam_post_blocked_flag or is_bugteam_disabled_via_env()


def _resolve_codex_down(
    is_codex_down_flag: bool, all_job_state_fields: dict[str, object]
) -> bool:
    """Combine --codex-down, env opt-out, and sticky job-state ``codex_down``.

    ::

        flag True, env unset, job unset             -> True   (caller passed the flag)
        flag False, reviews-disabled lists codex    -> True   (exported token)
        flag False, env unset, job codex_down true  -> True   (sticky job-state)
        flag False, env unset, job unset or false   -> False  (gate may run)

    The mark-ready blocker hook re-runs this script with no flags, so the env
    token and sticky job-state ``codex_down`` both carry the bypass into that
    re-check when the original run cannot re-pass ``--codex-down``.

    Args:
        is_codex_down_flag: True when the caller passed ``--codex-down``.
        all_job_state_fields: Parsed job-dir state, empty when none is readable.

    Returns:
        True when any of the three bypass sources is in force.
    """
    return (
        is_codex_down_flag
        or is_codex_disabled_via_env()
        or _read_codex_down_from_job_state(all_job_state_fields)
    )


def main(
    all_arguments: list[str],
    bugbot_bypass_note: str = BUGBOT_DOWN_BYPASS_NOTE,
    copilot_bypass_note: str = COPILOT_DOWN_BYPASS_NOTE,
) -> int:
    """Run the script end-to-end against parsed CLI arguments.

    Args:
        all_arguments: Argument list excluding the program name.
        bugbot_bypass_note: Note printed when the bugbot gate is bypassed.
        copilot_bypass_note: Note printed when the Copilot gates are bypassed.

    Returns:
        0 on full convergence, 1 on one or more gate failures.
    """
    arguments = parse_arguments(all_arguments)
    all_job_state_fields = _read_job_state()
    is_bugteam_post_blocked = _resolve_bugteam_post_blocked(arguments.bugteam_post_blocked)
    is_codex_down = _resolve_codex_down(arguments.codex_down, all_job_state_fields)
    fixture_path = getattr(arguments, "fixture", None)
    if fixture_path:
        bugbot_waiver = _waiver_from_cli_flag(
            arguments.bugbot_down, bugbot_bypass_note
        )
        copilot_waiver = _waiver_from_cli_flag(
            arguments.copilot_down, copilot_bypass_note
        )
        fixture = _load_convergence_fixture(Path(fixture_path))
        return _check_all_from_fixture(
            owner=arguments.owner,
            repo=arguments.repo,
            number=getattr(arguments, "pr_number"),
            fixture=fixture,
            is_bugbot_down=bugbot_waiver.is_waived,
            is_copilot_down=copilot_waiver.is_waived,
            is_bugteam_post_blocked=is_bugteam_post_blocked,
            is_codex_down=is_codex_down,
            bugbot_bypass_note=bugbot_waiver.bypass_note or bugbot_bypass_note,
            copilot_bypass_note=copilot_waiver.bypass_note or copilot_bypass_note,
        )
    bugbot_waiver = _resolve_bugbot_waiver(arguments.bugbot_down)
    copilot_waiver = _resolve_copilot_waiver(arguments.copilot_down)
    return check_all(
        owner=arguments.owner,
        repo=arguments.repo,
        number=getattr(arguments, "pr_number"),
        is_bugbot_down=bugbot_waiver.is_waived,
        is_copilot_down=copilot_waiver.is_waived,
        is_bugteam_post_blocked=is_bugteam_post_blocked,
        is_codex_down=is_codex_down,
        live_codex_clean_at=_resolve_live_codex_clean_at(
            arguments.codex_clean_at, all_job_state_fields
        ),
        bugbot_bypass_note=bugbot_waiver.bypass_note or bugbot_bypass_note,
        copilot_bypass_note=copilot_waiver.bypass_note or copilot_bypass_note,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
