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
the bugteam CLEAN-review gate.

Each flag also honors its own reviews-disabled token: "bugbot", "copilot",
or "bugteam". A caller that cannot pass the flag reaches the same bypass by
exporting the token. The mark-ready blocker hook re-runs this script with no
flags, so its convergence re-check reads the bypass from the exported token
instead.
"""

from __future__ import annotations

import argparse
import json
import sys
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
from pr_converge_scripts_constants.convergence_gate_constants import (
    FIXTURE_DEFAULT_PENDING_DETAIL,
    FIXTURE_DEFAULT_THREADS_DETAIL,
    FIXTURE_KEY_HEAD_SHA,
    FIXTURE_KEY_PENDING_REVIEWS_DETAIL,
    FIXTURE_KEY_PENDING_REVIEWS_PASSED,
    FIXTURE_KEY_PR_OBJECT,
    FIXTURE_KEY_REVIEWS,
    FIXTURE_KEY_UNRESOLVED_BOT_THREADS_DETAIL,
    FIXTURE_KEY_UNRESOLVED_BOT_THREADS_PASSED,
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
    is_copilot_disabled_via_env,
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


class GateContext(NamedTuple):
    """The PR coordinates and per-reviewer bypass flags one gate run evaluates."""

    owner: str
    repo: str
    number: int
    head_sha: str
    is_bugbot_down: bool
    is_copilot_down: bool
    is_bugteam_post_blocked: bool
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


def _bugbot_conditions(context: GateContext) -> list[GateCondition]:
    """Build the Bugbot gate conditions, bypassed when Bugbot is down."""
    if context.is_bugbot_down:
        return [("bugbot_clean_at == current_head", (True, "bypassed (bugbot_down)"))]
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
        return ("copilot_clean_at == current_head", (True, "bypassed (copilot_down)"))
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


def _pending_reviews_condition(context: GateContext) -> GateCondition:
    """Build the pending-requested-reviews condition, bypassed when Copilot is down."""
    if context.is_copilot_down:
        return ("no pending requested reviews", (True, "bypassed (copilot_down)"))
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
    is_threads_ok = payload.get(FIXTURE_KEY_UNRESOLVED_BOT_THREADS_PASSED, False)
    threads_detail = payload.get(
        FIXTURE_KEY_UNRESOLVED_BOT_THREADS_DETAIL, FIXTURE_DEFAULT_THREADS_DETAIL
    )
    is_pending_ok = payload.get(FIXTURE_KEY_PENDING_REVIEWS_PASSED, False)
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
    return ConvergenceFixture(
        head_sha=head_sha,
        pr_object=pr_object,
        reviews=typed_reviews,
        is_zero_unresolved_bot_threads=is_threads_ok,
        unresolved_bot_threads_detail=threads_detail,
        is_no_pending_reviews=is_pending_ok,
        pending_reviews_detail=pending_detail,
    )


def check_all(
    owner: str,
    repo: str,
    number: int,
    is_bugbot_down: bool,
    is_copilot_down: bool,
    is_bugteam_post_blocked: bool,
) -> int:
    """Run every convergence gate and print one PASS/FAIL line per condition.

    Args:
        owner: GitHub repository owner login.
        repo: GitHub repository name.
        number: Pull request number to inspect.
        is_bugbot_down: True bypasses the bugbot check-run and review-body gates.
        is_copilot_down: True bypasses the Copilot review and pending gates.
        is_bugteam_post_blocked: True skips the bugteam CLEAN-review gate.

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
    return parser


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the convergence checker.

    Args:
        all_argv: Argument list excluding the program name.

    Returns:
        Namespace exposing owner, repo, pr_number, fixture, bugbot_down, copilot_down,
        and bugteam_post_blocked attributes.
    """
    return _build_argument_parser().parse_args(all_argv)


def _resolve_bugbot_down(is_bugbot_down_flag: bool) -> bool:
    """Combine the --bugbot-down flag with the env availability gate for Bugbot."""
    return is_bugbot_down_flag or is_bugbot_disabled_via_env()


def _resolve_copilot_down(is_copilot_down_flag: bool) -> bool:
    """Combine the --copilot-down flag with the CLAUDE_REVIEWS_DISABLED env opt-out."""
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


def main(all_arguments: list[str]) -> int:
    """Run the script end-to-end against parsed CLI arguments.

    Args:
        all_arguments: Argument list excluding the program name.

    Returns:
        0 on full convergence, 1 on one or more gate failures.
    """
    arguments = parse_arguments(all_arguments)
    is_bugbot_down = _resolve_bugbot_down(arguments.bugbot_down)
    is_copilot_down = _resolve_copilot_down(arguments.copilot_down)
    is_bugteam_post_blocked = _resolve_bugteam_post_blocked(arguments.bugteam_post_blocked)
    fixture_path = getattr(arguments, "fixture", None)
    if fixture_path:
        fixture = _load_convergence_fixture(Path(fixture_path))
        return _check_all_from_fixture(
            owner=arguments.owner,
            repo=arguments.repo,
            number=getattr(arguments, "pr_number"),
            fixture=fixture,
            is_bugbot_down=is_bugbot_down,
            is_copilot_down=is_copilot_down,
            is_bugteam_post_blocked=is_bugteam_post_blocked,
        )
    return check_all(
        owner=arguments.owner,
        repo=arguments.repo,
        number=getattr(arguments, "pr_number"),
        is_bugbot_down=is_bugbot_down,
        is_copilot_down=is_copilot_down,
        is_bugteam_post_blocked=is_bugteam_post_blocked,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
