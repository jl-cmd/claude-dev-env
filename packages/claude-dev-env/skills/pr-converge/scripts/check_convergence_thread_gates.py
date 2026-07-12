"""Review-thread and pending-reviewer IO leaves for the convergence gate checks.

Each function issues one ``gh`` call (GraphQL or REST) and returns a
``(passed, detail)`` pair the convergence checker turns into a PASS/FAIL line.
The checker re-imports these names, so a test patches them on the checker module.
"""

from __future__ import annotations

import json

import _pr_converge_path_setup  # noqa: F401
from check_convergence_gates import (
    JsonObject,
    ReviewStateGroup,
    _gh_api,
    _run_gh_command,
)
from pr_converge_skill_constants.constants import (
    CLAUDE_LOGIN_FILTER_SUBSTRING,
    COPILOT_LOGIN_FILTER_SUBSTRING,
    COPILOT_REVIEWER_LOGIN,
    CURSOR_LOGIN_FILTER_SUBSTRING,
    GH_REQUESTED_REVIEWERS_PATH_TEMPLATE,
    GRAPHQL_REVIEW_THREADS_PAGE_SIZE,
    UNRESOLVED_THREAD_DETAIL_MAX,
)
from pr_converge_scripts_constants.convergence_gate_constants import (
    GRAPHQL_REVIEW_THREADS_QUERY,
    PENDING_REVIEWER_JOIN_SEPARATOR,
    THREAD_PATH_JOIN_SEPARATOR,
)


def _gh_graphql(query: str, variables: JsonObject) -> tuple[int, str]:
    """Run a ``gh api graphql`` query with variables and return returncode and stdout."""
    all_arguments: list[str] = ["gh", "api", "graphql", "-f", f"query={query}"]
    for each_key, each_variable in variables.items():
        if each_variable is None:
            continue
        flag = "-F" if isinstance(each_variable, int) else "-f"
        all_arguments.extend([flag, f"{each_key}={each_variable}"])
    return _run_gh_command(all_arguments)


def _thread_author_login(thread: JsonObject) -> str:
    """Return the login of a review thread's first comment author, or empty string."""
    comments_wrapper = thread.get("comments", {})
    if not isinstance(comments_wrapper, dict):
        return ""
    comments_nodes = comments_wrapper.get("nodes", [])
    if not isinstance(comments_nodes, list) or not comments_nodes:
        return ""
    first_comment = comments_nodes[0]
    author_wrapper = (
        first_comment.get("author") if isinstance(first_comment, dict) else None
    )
    if not isinstance(author_wrapper, dict):
        return ""
    login = author_wrapper.get("login", "")
    return login if isinstance(login, str) else ""


def _is_unresolved_bot_thread(thread: JsonObject, bot_logins: ReviewStateGroup) -> bool:
    """Return whether a review thread is unresolved, current, and bot-authored."""
    if thread.get("isResolved") is True or thread.get("isOutdated") is True:
        return False
    login = _thread_author_login(thread).lower()
    return any(each_bot in login for each_bot in bot_logins)


def _unresolved_bot_threads_in_page(
    nodes: object, bot_logins: ReviewStateGroup
) -> list[JsonObject]:
    """Return the unresolved bot-authored threads among one page of thread nodes."""
    if not isinstance(nodes, list):
        return []
    return [
        each_thread
        for each_thread in nodes
        if isinstance(each_thread, dict)
        and _is_unresolved_bot_thread(each_thread, bot_logins)
    ]


def _review_threads_container(graphql_payload: object) -> JsonObject | None:
    """Return the ``reviewThreads`` object from a GraphQL payload, or None."""
    if not isinstance(graphql_payload, dict):
        return None
    envelope = graphql_payload.get("data", {})
    repository = envelope.get("repository", {}) if isinstance(envelope, dict) else {}
    pull_request = (
        repository.get("pullRequest", {}) if isinstance(repository, dict) else {}
    )
    threads = (
        pull_request.get("reviewThreads", {}) if isinstance(pull_request, dict) else {}
    )
    return threads if isinstance(threads, dict) else None


def _fetch_review_threads_page(
    *, owner: str, repo: str, number: int, cursor: str | None
) -> tuple[str, object, object]:
    """Fetch one page of review threads and return an error text, nodes, and page info."""
    variables: JsonObject = {
        "owner": owner,
        "repo": repo,
        "number": number,
        "first": GRAPHQL_REVIEW_THREADS_PAGE_SIZE,
        "cursor": cursor,
    }
    returncode, stdout = _gh_graphql(GRAPHQL_REVIEW_THREADS_QUERY, variables)
    if returncode != 0:
        return f"gh api graphql error: {stdout}", [], {}
    try:
        graphql_payload = json.loads(stdout)
    except json.JSONDecodeError:
        return "gh api graphql response not valid JSON", [], {}
    threads = _review_threads_container(graphql_payload)
    if threads is None:
        return "unexpected GraphQL response shape", [], {}
    return "", threads.get("nodes", []), threads.get("pageInfo", {})


def _next_thread_cursor(page_info: object) -> str | None:
    """Return the next pagination cursor, or None when there is no next page."""
    if not isinstance(page_info, dict):
        return None
    if not page_info.get("hasNextPage"):
        return None
    next_cursor = page_info.get("endCursor")
    return next_cursor if isinstance(next_cursor, str) else None


def _format_unresolved_detail(all_unresolved: list[JsonObject]) -> str:
    """Format the unresolved-thread count and a bounded list of their paths."""
    detail_parts = [
        str(each_thread.get("path", "?"))
        for each_thread in all_unresolved[:UNRESOLVED_THREAD_DETAIL_MAX]
    ]
    detail_text = THREAD_PATH_JOIN_SEPARATOR.join(detail_parts)
    if len(all_unresolved) > UNRESOLVED_THREAD_DETAIL_MAX:
        detail_text += (
            f" ... and {len(all_unresolved) - UNRESOLVED_THREAD_DETAIL_MAX} more"
        )
    return f"{len(all_unresolved)} unresolved ({detail_text})"


def _count_unresolved_bot_threads(
    *, owner: str, repo: str, number: int
) -> tuple[bool, str]:
    """Return whether zero unresolved bot review threads remain on the PR."""
    bot_logins = (
        CURSOR_LOGIN_FILTER_SUBSTRING,
        CLAUDE_LOGIN_FILTER_SUBSTRING,
        COPILOT_LOGIN_FILTER_SUBSTRING,
    )
    all_unresolved: list[JsonObject] = []
    cursor: str | None = None
    while True:
        error_text, nodes, page_info = _fetch_review_threads_page(
            owner=owner, repo=repo, number=number, cursor=cursor
        )
        if error_text:
            return False, error_text
        all_unresolved.extend(_unresolved_bot_threads_in_page(nodes, bot_logins))
        cursor = _next_thread_cursor(page_info)
        if cursor is None:
            break
    if not all_unresolved:
        return True, "0 unresolved"
    return False, _format_unresolved_detail(all_unresolved)


def _requested_reviewer_users(pending_payload: object) -> list[object]:
    if isinstance(pending_payload, dict):
        users = pending_payload.get("users", [])
    elif isinstance(pending_payload, list):
        users = pending_payload
    else:
        return []
    return users if isinstance(users, list) else []


def _pending_copilot_logins(all_users: list[object]) -> list[str]:
    """Return the Copilot reviewer logins still pending among requested reviewers."""
    pending: list[str] = []
    for each_user in all_users:
        if not isinstance(each_user, dict):
            continue
        login = each_user.get("login", "")
        if isinstance(login, str) and COPILOT_REVIEWER_LOGIN.lower() in login.lower():
            pending.append(login)
    return pending


def _check_no_pending_reviews(
    *, owner: str, repo: str, number: int
) -> tuple[bool, str]:
    """Return whether no Copilot review request is still pending on the PR."""
    endpoint = GH_REQUESTED_REVIEWERS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    returncode, stdout = _gh_api(endpoint)
    if returncode != 0:
        return False, f"gh api error: {stdout}"
    try:
        pending_payload = json.loads(stdout)
    except json.JSONDecodeError:
        return True, "no pending (empty response)"
    copilot_pending = _pending_copilot_logins(
        _requested_reviewer_users(pending_payload)
    )
    if copilot_pending:
        return (
            False,
            f"pending: {PENDING_REVIEWER_JOIN_SEPARATOR.join(copilot_pending)}",
        )
    return True, "no pending reviewers"
