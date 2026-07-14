"""Review and Bugbot IO leaves for the convergence gate checks.

Each function issues one ``gh`` REST call and returns a ``(passed, detail)``
pair the convergence checker turns into a PASS/FAIL line, or a raw
``(returncode, stdout)`` pair for the low-level callers. The checker re-imports
these names, so a test patches them on the checker module.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

import _pr_converge_path_setup  # noqa: F401
from pr_converge_skill_constants.constants import (
    ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS,
    BUGBOT_CHECK_RUN_NAME_SUBSTRING,
    BUGBOT_DIRTY_BODY_REGEX,
    CHECK_RUNS_PER_PAGE,
    CURSOR_LOGIN_FILTER_SUBSTRING,
    EXIT_CODE_GH_ERROR,
    GH_CHECK_RUNS_PATH_TEMPLATE,
    GH_PR_OBJECT_PATH_TEMPLATE,
    GH_REVIEWS_PATH_TEMPLATE,
    REVIEWS_PER_PAGE,
)
from pr_converge_scripts_constants.convergence_gate_constants import (
    MERGEABLE_STATE_CLEAN,
    SHORT_SHA_LENGTH,
)

JsonObject = dict[str, object]
ReviewStateGroup = tuple[str, ...]


def _run_gh_command(all_arguments: list[str]) -> tuple[int, str]:
    completed_process = subprocess.run(
        all_arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed_process.returncode, completed_process.stdout


def _gh_api(endpoint_path: str) -> tuple[int, str]:
    return _run_gh_command(["gh", "api", endpoint_path])


def _gh_api_paginated(endpoint_path: str) -> tuple[int, str]:
    return _run_gh_command(["gh", "api", endpoint_path, "--paginate", "--slurp"])


def _short_sha(commit_id: str) -> str:
    return commit_id[:SHORT_SHA_LENGTH]


def _get_pr_head_sha(*, owner: str, repo: str, number: int) -> str:
    """Return the PR HEAD SHA, exiting with the gh-error code when the call fails."""
    endpoint = GH_PR_OBJECT_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api(endpoint)
    if returncode != 0:
        sys.stderr.write(f"gh api error fetching PR object: {stdout}\n")
        raise SystemExit(EXIT_CODE_GH_ERROR)
    try:
        pr_object = json.loads(stdout)
    except json.JSONDecodeError:
        sys.stderr.write("gh api PR object response not valid JSON\n")
        raise SystemExit(EXIT_CODE_GH_ERROR) from None
    if not isinstance(pr_object, dict):
        raise SystemExit(EXIT_CODE_GH_ERROR)
    head_object = pr_object.get("head")
    if not isinstance(head_object, dict):
        raise SystemExit(EXIT_CODE_GH_ERROR)
    head_sha: object = head_object.get("sha")
    if not isinstance(head_sha, str):
        raise SystemExit(EXIT_CODE_GH_ERROR)
    return head_sha


def _evaluate_mergeable_from_pr_object(pr_object: JsonObject) -> tuple[bool, str]:
    """Return whether a PR object dict is cleanly mergeable.

    Pure evaluator: no network IO. Live and fixture paths share this contract.

    Args:
        pr_object: Pull request JSON object with mergeable and mergeable_state fields.

    Returns:
        (True, clean) when mergeable is true and state is clean; otherwise (False, state).
    """
    mergeable: object = pr_object.get("mergeable")
    mergeable_state: object = pr_object.get("mergeable_state", "unknown")
    state_text = str(mergeable_state)
    if mergeable is True and state_text == MERGEABLE_STATE_CLEAN:
        return True, MERGEABLE_STATE_CLEAN
    return False, state_text


def _get_mergeable(*, owner: str, repo: str, number: int) -> tuple[bool, str]:
    """Return whether the PR is cleanly mergeable, with the mergeable-state detail."""
    endpoint = GH_PR_OBJECT_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api(endpoint)
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    try:
        pr_object = json.loads(stdout)
    except json.JSONDecodeError:
        return False, "gh api response not valid JSON"
    if not isinstance(pr_object, dict):
        return False, "unknown"
    return _evaluate_mergeable_from_pr_object(pr_object)


def _bugbot_check_runs(
    *, owner: str, repo: str, sha: str
) -> tuple[int, list[JsonObject]]:
    """Fetch the check runs for a SHA and return the returncode and run dicts."""
    endpoint = GH_CHECK_RUNS_PATH_TEMPLATE.format(owner=owner, repo=repo, sha=sha)
    returncode, stdout = _gh_api(f"{endpoint}?per_page={CHECK_RUNS_PER_PAGE}")
    if returncode != 0:
        return returncode, []
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return returncode, []
    raw_runs = payload.get("check_runs") if isinstance(payload, dict) else None
    if not isinstance(raw_runs, list):
        return returncode, []
    return returncode, [each_run for each_run in raw_runs if isinstance(each_run, dict)]


def _bugbot_run_conclusion_detail(check_run: JsonObject) -> tuple[bool, str]:
    """Return the pass flag and detail for one bugbot check run."""
    conclusion = check_run.get("conclusion", "")
    if conclusion in ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS:
        check_id = check_run.get("id", "?")
        detail_url = check_run.get("html_url", "")
        details_suffix = f" ({detail_url})" if detail_url else ""
        return True, f"check run {check_id}, conclusion: {conclusion}{details_suffix}"
    return (
        False,
        f"check run conclusion is '{conclusion}', expected {ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS}",
    )


def _check_bugbot(*, owner: str, repo: str, sha: str) -> tuple[bool, str]:
    """Return whether the Cursor Bugbot check run on a SHA completed successfully."""
    returncode, check_runs = _bugbot_check_runs(owner=owner, repo=repo, sha=sha)
    if returncode != 0:
        return False, "gh api error fetching check runs"
    for each_check_run in check_runs:
        each_name = each_check_run.get("name", "")
        if not isinstance(each_name, str):
            continue
        if BUGBOT_CHECK_RUN_NAME_SUBSTRING.lower() not in each_name.lower():
            continue
        return _bugbot_run_conclusion_detail(each_check_run)
    return False, "no bugbot check run found"


def _flatten_paginated_reviews(stdout: str) -> list[JsonObject] | None:
    """Flatten a slurped, paginated reviews payload into a newest-first list."""
    try:
        reviews_payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(reviews_payload, list):
        return None
    all_flat: list[JsonObject] = [
        each_entry
        for each_page in reviews_payload
        if isinstance(each_page, list)
        for each_entry in each_page
        if isinstance(each_entry, dict)
    ]
    all_flat.sort(
        key=lambda each_review: str(each_review.get("submitted_at", "")), reverse=True
    )
    return all_flat


def _review_matches_login(review: JsonObject, login_substring: str) -> bool:
    user_object = review.get("user")
    if not isinstance(user_object, dict):
        return False
    login = user_object.get("login", "")
    return isinstance(login, str) and login_substring in login.lower()


def _review_commit_starts_with(review: JsonObject, head_sha: str) -> bool:
    commit_id = review.get("commit_id", "")
    return isinstance(commit_id, str) and commit_id.startswith(head_sha)


def _check_bugbot_not_dirty(
    *, owner: str, repo: str, number: int, head_sha: str
) -> tuple[bool, str]:
    """Return whether the newest Cursor Bugbot review on HEAD reports no findings."""
    endpoint = GH_REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api_paginated(f"{endpoint}?per_page={REVIEWS_PER_PAGE}")
    if returncode != 0:
        return True, "bugbot reviews unavailable (non-fatal)"
    all_flat = _flatten_paginated_reviews(stdout)
    if all_flat is None:
        return True, "bugbot reviews not valid JSON (non-fatal)"
    dirty_pattern = re.compile(BUGBOT_DIRTY_BODY_REGEX, re.IGNORECASE)
    for each_review in all_flat:
        if not _review_matches_login(each_review, CURSOR_LOGIN_FILTER_SUBSTRING):
            continue
        if not _review_commit_starts_with(each_review, head_sha):
            continue
        body = each_review.get("body", "")
        if isinstance(body, str) and dirty_pattern.search(body):
            return False, "bugbot review body reports findings"
        return True, "clean"
    return True, "no bugbot review at HEAD"


def _bot_review_state_detail(
    review: JsonObject,
    clean_states: ReviewStateGroup,
    dirty_states: ReviewStateGroup,
) -> tuple[bool, str]:
    """Return the pass flag and detail for one bot review's state."""
    review_state = review.get("state", "")
    commit_id = review.get("commit_id", "")
    short_commit = _short_sha(commit_id) if isinstance(commit_id, str) else "?"
    if review_state in clean_states:
        review_id = review.get("id", "?")
        return True, f"review {review_id}, state: {review_state}, commit {short_commit}"
    if review_state in dirty_states:
        return False, f"review state is '{review_state}' (dirty), commit {short_commit}"
    return False, f"review state is '{review_state}', commit {short_commit}"


def _check_bot_review(
    *,
    owner: str,
    repo: str,
    number: int,
    head_sha: str,
    login_substring: str,
    clean_states: ReviewStateGroup,
    dirty_states: ReviewStateGroup,
    label: str,
) -> tuple[bool, str]:
    """Return whether the newest matching bot review on HEAD is in a clean state."""
    endpoint = GH_REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
    returncode, stdout = _gh_api_paginated(f"{endpoint}?per_page={REVIEWS_PER_PAGE}")
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    all_flat = _flatten_paginated_reviews(stdout)
    if all_flat is None:
        return False, f"no {label} review found"
    for each_review in all_flat:
        if not _review_matches_login(each_review, login_substring):
            continue
        if not _review_commit_starts_with(each_review, head_sha):
            continue
        return _bot_review_state_detail(each_review, clean_states, dirty_states)
    return False, f"no {label} review found on {_short_sha(head_sha)}"
