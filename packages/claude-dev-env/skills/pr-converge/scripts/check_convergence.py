"""Verify every convergence pre-condition for a PR before marking it ready.

::

    check_convergence.py --owner O --repo R --pr-number N [flags]
        exit 0  ok:   every gate passed — safe to mark ready
        exit 1  flag: a gate failed (FAIL lines print to stdout)
        exit 2  flag: gh CLI error

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
import sys
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
)
from check_convergence_thread_gates import (
    _check_no_pending_reviews,
    _count_unresolved_bot_threads,
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


class GateContext(NamedTuple):
    """The PR coordinates and per-reviewer bypass flags one gate run evaluates."""

    owner: str
    repo: str
    number: int
    head_sha: str
    is_bugbot_down: bool
    is_copilot_down: bool
    is_bugteam_post_blocked: bool


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


def _check_bugteam_clean(*, owner: str, repo: str, number: int, head_sha: str) -> tuple[bool, str]:
    """Return whether the newest bugteam audit review on HEAD declares a clean pass."""
    endpoint = GH_REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api_paginated(f"{endpoint}?per_page={REVIEWS_PER_PAGE}")
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    all_flat = _flatten_paginated_reviews(stdout)
    if all_flat is None:
        return False, "unexpected gh api response shape (expected list)"
    for each_review in all_flat:
        detail = _bugteam_review_detail(each_review, head_sha)
        if detail is not None:
            return detail
    return False, f"no bugteam review found on {_short_sha(head_sha)}"


def _bugbot_conditions(context: GateContext) -> list[GateCondition]:
    """Build the Bugbot gate conditions, bypassed when Bugbot is down."""
    if context.is_bugbot_down:
        return [("bugbot_clean_at == current_head", (True, "bypassed (bugbot_down)"))]
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
                    owner=context.owner, repo=context.repo, number=context.number, head_sha=context.head_sha
                ),
            )
        )
    return conditions


def _bugteam_condition(context: GateContext) -> GateCondition:
    """Build the bugteam CLEAN-review condition, skipped when the post was blocked."""
    if context.is_bugteam_post_blocked:
        return ("bugteam_clean_at == current_head", (True, "bypassed (bugteam_post_blocked)"))
    return (
        "bugteam_clean_at == current_head",
        _check_bugteam_clean(
            owner=context.owner, repo=context.repo, number=context.number, head_sha=context.head_sha
        ),
    )


def _copilot_review_condition(context: GateContext) -> GateCondition:
    """Build the Copilot review gate condition, bypassed when Copilot is down."""
    if context.is_copilot_down:
        return ("copilot_clean_at == current_head", (True, "bypassed (copilot_down)"))
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
    return (
        "no pending requested reviews",
        _check_no_pending_reviews(owner=context.owner, repo=context.repo, number=context.number),
    )


def _state_conditions(context: GateContext) -> list[GateCondition]:
    """Build the thread, mergeable, and pending-review conditions in gate order."""
    return [
        (
            "zero unresolved bot threads",
            _count_unresolved_bot_threads(owner=context.owner, repo=context.repo, number=context.number),
        ),
        ("PR is mergeable", _get_mergeable(owner=context.owner, repo=context.repo, number=context.number)),
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


def check_all(
    owner: str,
    repo: str,
    number: int,
    is_bugbot_down: bool,
    is_copilot_down: bool,
    is_bugteam_post_blocked: bool = False,
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
    )
    return _evaluate_convergence(context)


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the convergence checker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--pr-number", required=True, type=int, help="Pull request number")
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
        Namespace exposing owner, repo, pr_number, bugbot_down, copilot_down,
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
    return check_all(
        owner=arguments.owner,
        repo=arguments.repo,
        number=getattr(arguments, "pr_number"),
        is_bugbot_down=_resolve_bugbot_down(arguments.bugbot_down),
        is_copilot_down=_resolve_copilot_down(arguments.copilot_down),
        is_bugteam_post_blocked=_resolve_bugteam_post_blocked(arguments.bugteam_post_blocked),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
