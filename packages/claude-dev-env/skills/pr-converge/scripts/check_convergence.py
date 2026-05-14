"""Verify all convergence pre-conditions for a PR before marking ready.

Usage:
  python scripts/check_convergence.py --owner <O> --repo <R> --pr-number <N>

Exit codes:
  0 — all seven pre-conditions met
  1 — one or more conditions not met (FAIL lines printed to stdout)
  2 — gh CLI error
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_pr_converge_dir = Path(__file__).resolve().parent.parent
if str(_pr_converge_dir) not in sys.path:
    sys.path.insert(0, str(_pr_converge_dir))

from config.constants import (
    ALL_CLAUDE_DIRTY_REVIEW_STATES,
    ALL_COPILOT_DIRTY_REVIEW_STATES,
    ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS,
    BUGBOT_CHECK_RUN_NAME_SUBSTRING,
    BUGBOT_DIRTY_BODY_REGEX,
    CHECK_RUNS_PER_PAGE,
    ALL_CLAUDE_CLEAN_REVIEW_STATES,
    CLAUDE_LOGIN_FILTER_SUBSTRING,
    ALL_COPILOT_CLEAN_REVIEW_STATES,
    COPILOT_LOGIN_FILTER_SUBSTRING,
    COPILOT_REVIEWER_LOGIN,
    CURSOR_LOGIN_FILTER_SUBSTRING,
    EXIT_CODE_GH_ERROR,
    GH_CHECK_RUNS_PATH_TEMPLATE,
    GH_PR_OBJECT_PATH_TEMPLATE,
    GH_REQUESTED_REVIEWERS_PATH_TEMPLATE,
    GH_REVIEWS_PATH_TEMPLATE,
    GRAPHQL_REVIEW_THREADS_PAGE_SIZE,
    REVIEWS_PER_PAGE,
    UNRESOLVED_THREAD_DETAIL_MAX,
)


def _gh_api(endpoint_path: str) -> tuple[int, str]:
    completed_process = subprocess.run(
        ["gh", "api", endpoint_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed_process.returncode, completed_process.stdout


def _gh_api_paginated(endpoint_path: str) -> tuple[int, str]:
    completed_process = subprocess.run(
        ["gh", "api", endpoint_path, "--paginate", "--slurp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed_process.returncode, completed_process.stdout


def _get_pr_head_sha(*, owner: str, repo: str, number: int) -> str:
    endpoint = GH_PR_OBJECT_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api(endpoint)
    if returncode != 0:
        print(f"gh api error fetching PR object: {stdout}", file=sys.stderr)
        raise SystemExit(EXIT_CODE_GH_ERROR)
    pr_object = json.loads(stdout)
    head_sha: object = pr_object.get("head", {}).get("sha")
    if not isinstance(head_sha, str):
        raise SystemExit(EXIT_CODE_GH_ERROR)
    return head_sha


def _get_mergeable(*, owner: str, repo: str, number: int) -> tuple[bool, str]:
    endpoint = GH_PR_OBJECT_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api(endpoint)
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    pr_object = json.loads(stdout)
    mergeable: object = pr_object.get("mergeable")
    mergeable_state: object = pr_object.get("mergeable_state", "unknown")
    state_str = str(mergeable_state)
    if mergeable is True and state_str == "clean":
        return True, "clean"
    return False, state_str


def _check_bugbot(*, owner: str, repo: str, sha: str) -> tuple[bool, str]:
    endpoint = GH_CHECK_RUNS_PATH_TEMPLATE.format(owner=owner, repo=repo, sha=sha)
    returncode, stdout = _gh_api(f"{endpoint}?per_page={CHECK_RUNS_PER_PAGE}")
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    try:
        response_body = json.loads(stdout)
    except json.JSONDecodeError:
        return False, "gh api response not valid JSON"
    check_runs: list[dict[str, object]] = []
    if isinstance(response_body, dict):
        raw_runs = response_body.get("check_runs")
        if isinstance(raw_runs, list):
            check_runs = [r for r in raw_runs if isinstance(r, dict)]
    for check_entry in check_runs:
        each_name = check_entry.get("name", "")
        if not isinstance(each_name, str):
            continue
        if BUGBOT_CHECK_RUN_NAME_SUBSTRING.lower() not in each_name.lower():
            continue
        conclusion = check_entry.get("conclusion", "")
        if conclusion in ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS:
            check_id = check_entry.get("id", "?")
            detail_url = check_entry.get("html_url", "")
            details_suffix = f" ({detail_url})" if detail_url else ""
            return True, f"check run #{check_id}, conclusion: {conclusion}{details_suffix}"
        return False, f"check run conclusion is '{conclusion}', expected {ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS}"
    return False, "no bugbot check run found"


def _check_bugbot_not_dirty(*, owner: str, repo: str, number: int, head_sha: str) -> tuple[bool, str]:
    endpoint = GH_REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api_paginated(f"{endpoint}?per_page={REVIEWS_PER_PAGE}")
    if returncode != 0:
        return True, "bugbot reviews unavailable (non-fatal)"
    try:
        raw_output = json.loads(stdout)
    except json.JSONDecodeError:
        return True, "bugbot reviews not valid JSON (non-fatal)"
    if not isinstance(raw_output, list):
        return True, "no reviews"
    all_pages = [p for p in raw_output if isinstance(p, list)]
    all_flat: list[dict[str, object]] = [
        each_entry
        for page in all_pages
        for each_entry in page
        if isinstance(each_entry, dict)
    ]
    all_flat.sort(
        key=lambda each_review: str(each_review.get("submitted_at", "")),
        reverse=True,
    )
    dirty_pattern = re.compile(BUGBOT_DIRTY_BODY_REGEX, re.IGNORECASE)
    for each_review in all_flat:
        user_obj = each_review.get("user")
        if not isinstance(user_obj, dict):
            continue
        login = user_obj.get("login", "")
        if not isinstance(login, str):
            continue
        if CURSOR_LOGIN_FILTER_SUBSTRING not in login.lower():
            continue
        commit_id = each_review.get("commit_id", "")
        if not isinstance(commit_id, str) or not commit_id.startswith(head_sha):
            continue
        body = each_review.get("body", "")
        if isinstance(body, str) and dirty_pattern.search(body):
            return False, "bugbot review body reports findings"
        return True, "clean"
    return True, "no bugbot review at HEAD"


def _check_bot_review(
    *,
    owner: str,
    repo: str,
    number: int,
    head_sha: str,
    login_substring: str,
    clean_states: tuple[str, ...],
    dirty_states: tuple[str, ...],
    label: str,
) -> tuple[bool, str]:
    endpoint = GH_REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api_paginated(f"{endpoint}?per_page={REVIEWS_PER_PAGE}")
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    try:
        raw_output = json.loads(stdout)
    except json.JSONDecodeError:
        return False, "gh api response not valid JSON"
    if not isinstance(raw_output, list):
        return False, f"no {label} review found"
    all_pages = [p for p in raw_output if isinstance(p, list)]
    all_flat = [
        each_entry
        for page in all_pages
        for each_entry in page
        if isinstance(each_entry, dict)
    ]
    all_flat.sort(
        key=lambda each_review: str(each_review.get("submitted_at", "")),
        reverse=True,
    )
    for each_review in all_flat:
        user_obj = each_review.get("user")
        if not isinstance(user_obj, dict):
            continue
        login = user_obj.get("login", "")
        if not isinstance(login, str):
            continue
        if login_substring not in login.lower():
            continue
        commit_id = each_review.get("commit_id", "")
        review_state = each_review.get("state", "")
        if not isinstance(commit_id, str) or not commit_id.startswith(head_sha):
            continue
        if review_state in clean_states:
            review_id = each_review.get("id", "?")
            return (
                True,
                f"review #{review_id}, state: {review_state}, commit: {commit_id[:7]}",
            )
        if review_state in dirty_states:
            return (
                False,
                f"review state is '{review_state}' (dirty), commit: {commit_id[:7]}",
            )
        return False, f"review state is '{review_state}', commit: {commit_id[:7]}"
    return False, f"no {label} review found on {head_sha[:7]}"


def _gh_graphql(query: str, variables: dict[str, object]) -> tuple[int, str]:
    args: list[str] = ["gh", "api", "graphql", "-f", f"query={query}"]
    for each_key, each_value in variables.items():
        if each_value is None:
            continue
        if isinstance(each_value, int):
            args.extend(["-F", f"{each_key}={each_value}"])
        else:
            args.extend(["-f", f"{each_key}={each_value}"])
    completed_process = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed_process.returncode, completed_process.stdout


def _count_unresolved_bot_threads(
    *, owner: str, repo: str, number: int
) -> tuple[bool, str]:
    query = """
query($owner: String!, $repo: String!, $number: Int!, $first: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: $first, after: $cursor) {
        nodes {
          isResolved
          isOutdated
          path
          comments(first: 1) {
            nodes {
              author { login }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""
    bot_logins = (
        CURSOR_LOGIN_FILTER_SUBSTRING,
        CLAUDE_LOGIN_FILTER_SUBSTRING,
        COPILOT_LOGIN_FILTER_SUBSTRING,
    )
    unresolved: list[dict[str, object]] = []
    cursor: str | None = None

    while True:
        variables: dict[str, object] = {
            "owner": owner,
            "repo": repo,
            "number": number,
            "first": GRAPHQL_REVIEW_THREADS_PAGE_SIZE,
            "cursor": cursor,
        }
        returncode, stdout = _gh_graphql(query, variables)
        if returncode != 0:
            return False, f"gh api graphql error: {stdout}"
        try:
            response_body = json.loads(stdout)
        except json.JSONDecodeError:
            return False, "gh api graphql response not valid JSON"
        response_data = response_body.get("data", {})
        repository = response_data.get("repository", {}) if isinstance(response_data, dict) else {}
        pull_request = repository.get("pullRequest", {}) if isinstance(repository, dict) else {}
        threads = pull_request.get("reviewThreads", {}) if isinstance(pull_request, dict) else {}
        if not isinstance(threads, dict):
            return False, "unexpected GraphQL response shape"
        nodes = threads.get("nodes", [])
        if isinstance(nodes, list):
            for each_thread in nodes:
                if not isinstance(each_thread, dict):
                    continue
                if each_thread.get("isResolved") is True:
                    continue
                if each_thread.get("isOutdated") is True:
                    continue
                comments_wrapper = each_thread.get("comments", {})
                if not isinstance(comments_wrapper, dict):
                    continue
                comments_nodes = comments_wrapper.get("nodes", [])
                if not isinstance(comments_nodes, list) or not comments_nodes:
                    continue
                first_comment = comments_nodes[0]
                if not isinstance(first_comment, dict):
                    continue
                author_wrapper = first_comment.get("author")
                if not isinstance(author_wrapper, dict):
                    continue
                login = author_wrapper.get("login", "")
                if not isinstance(login, str):
                    continue
                is_bot = any(bot in login.lower() for bot in bot_logins)
                if not is_bot:
                    continue
                unresolved.append(each_thread)
        page_info = threads.get("pageInfo", {})
        if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
            break
        next_cursor = page_info.get("endCursor")
        if isinstance(next_cursor, str):
            cursor = next_cursor
        else:
            break

    if not unresolved:
        return True, "0 unresolved"
    details_parts: list[str] = []
    for each_thread in unresolved[:UNRESOLVED_THREAD_DETAIL_MAX]:
        thread_path = each_thread.get("path", "?")
        details_parts.append(str(thread_path))
    detail_text = "; ".join(details_parts)
    if len(unresolved) > UNRESOLVED_THREAD_DETAIL_MAX:
        detail_text += f" ... and {len(unresolved) - UNRESOLVED_THREAD_DETAIL_MAX} more"
    return False, f"{len(unresolved)} unresolved ({detail_text})"


def _check_no_pending_reviews(
    *, owner: str, repo: str, number: int
) -> tuple[bool, str]:
    endpoint = GH_REQUESTED_REVIEWERS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    returncode, stdout = _gh_api(endpoint)
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    try:
        response_body = json.loads(stdout)
    except json.JSONDecodeError:
        return True, "no pending (empty response)"
    if isinstance(response_body, dict):
        users = response_body.get("users", [])
    elif isinstance(response_body, list):
        users = response_body
    else:
        return True, "no pending (unexpected format)"
    if not isinstance(users, list):
        return True, "no pending"
    copilot_pending = []
    for each_user in users:
        if not isinstance(each_user, dict):
            continue
        login = each_user.get("login", "")
        if isinstance(login, str) and COPILOT_REVIEWER_LOGIN.lower() in login.lower():
            copilot_pending.append(login)
    if copilot_pending:
        return False, f"pending: {', '.join(copilot_pending)}"
    return True, "no pending reviewers"


def check_all(*, owner: str, repo: str, number: int) -> int:
    head_sha = _get_pr_head_sha(owner=owner, repo=repo, number=number)
    print(f"HEAD: {head_sha[:7]}\n")

    conditions: list[tuple[str, tuple[bool, str]]] = []

    conditions.append(
        (
            "bugbot_clean_at == current_head",
            _check_bugbot(owner=owner, repo=repo, sha=head_sha),
        )
    )
    if conditions[-1][1][0]:
        conditions.append(
            (
                "bugbot review body clean",
                _check_bugbot_not_dirty(owner=owner, repo=repo, number=number, head_sha=head_sha),
            )
        )

    conditions.append(
        (
            "bugteam_clean_at == current_head",
            _check_bot_review(
                owner=owner,
                repo=repo,
                number=number,
                head_sha=head_sha,
                login_substring=CLAUDE_LOGIN_FILTER_SUBSTRING,
                clean_states=ALL_CLAUDE_CLEAN_REVIEW_STATES,
                dirty_states=ALL_CLAUDE_DIRTY_REVIEW_STATES,
                label="claude[bot]",
            ),
        )
    )

    conditions.append(
        (
            "copilot_clean_at == current_head",
            _check_bot_review(
                owner=owner,
                repo=repo,
                number=number,
                head_sha=head_sha,
                login_substring=COPILOT_LOGIN_FILTER_SUBSTRING,
                clean_states=ALL_COPILOT_CLEAN_REVIEW_STATES,
                dirty_states=ALL_COPILOT_DIRTY_REVIEW_STATES,
                label="copilot",
            ),
        )
    )

    conditions.append(
        (
            "zero unresolved bot threads",
            _count_unresolved_bot_threads(owner=owner, repo=repo, number=number),
        )
    )

    conditions.append(
        ("PR is mergeable", _get_mergeable(owner=owner, repo=repo, number=number))
    )

    conditions.append(
        (
            "no pending requested reviews",
            _check_no_pending_reviews(owner=owner, repo=repo, number=number),
        )
    )

    is_all_passed = True
    index = 1
    for label, (passed, detail) in conditions:
        status = "PASS" if passed else "FAIL"
        print(f"{index}. {label}: {status} — {detail}")
        if not passed:
            is_all_passed = False
        index += 1

    print()
    if is_all_passed:
        print("All pre-conditions met — PR is ready to mark ready.")
    else:
        print("One or more pre-conditions not met — do not mark ready.")
    return 0 if is_all_passed else 1


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument(
        "--pr-number", required=True, type=int, help="Pull request number"
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    arguments = parse_arguments(all_arguments)
    return check_all(
        owner=arguments.owner,
        repo=arguments.repo,
        number=getattr(arguments, "pr_number"),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
