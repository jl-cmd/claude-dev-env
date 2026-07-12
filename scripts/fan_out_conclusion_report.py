#!/usr/bin/env python3
"""Name each fan-out target's listener conclusion for one dispatch.

Runs after ``scripts/fan_out_dispatch.py`` in the fan-out workflow. It
re-enumerates the same target repos and logs one line per repo saying how this
dispatch's listener run finished, so a failed run names the repo rather than
vanishing into an aggregate count.

::

    public target   ->  ::notice::Target acme/widgets dispatch conclusion: succeeded
    private target  ->  ::notice::Target acme/[redacted:1a2b3c4d] dispatch conclusion: failed

A public target logs its owner and name. A private target, or one whose
visibility the enumeration did not report, logs its owner scope plus a short
sha256 prefix of the full name, so the operator can recompute the hash from
their own repo list while the private name stays out of a world-readable log.

The correlation floor comes from the ``DISPATCHED_AT`` environment variable the
workflow records just before the dispatch step. Absent that variable, the
report's own start time stands in as the floor. That time falls after the real
dispatch, so it risks dropping a listener run created before the report
launched, logging it as no-matching-run. The workflow always sets
``DISPATCHED_AT``, so this fallback covers only a standalone run with no
preceding dispatch.

A workflow lookup that returns neither 200 nor 404 reports as no-matching-run.
Only a 200 body is trusted. The reused HTTP helper does not tell an auth error
apart from a server error.
"""

import hashlib
import os
import sys
from datetime import datetime, timezone

import fan_out_dispatch
from config.constants import (
    ENV_DISPATCHED_AT,
    LISTENER_RUNS_QUERY_TEMPLATE,
    REDACTED_REPO_HASH_PREFIX_LENGTH,
    REDACTED_REPO_IDENTIFIER_TEMPLATE,
    REPO_CONCLUSION_LOG_TEMPLATE,
    REPO_FULL_NAME_SEPARATOR,
    REPORT_STATUS_FAILED,
    REPORT_STATUS_LISTENER_MISSING,
    REPORT_STATUS_NO_MATCHING_RUN,
    REPORT_STATUS_OPTED_OUT,
    REPORT_STATUS_SUCCEEDED,
)
from config.local_identity import fanout_owner_scopes, token_env_var_name


def redacted_repo_identifier(full_repo_name: str, is_private: bool) -> str:
    """Return a log-safe identifier for one target repo.

    ::

        redacted_repo_identifier("acme/widgets", is_private=False)  ->  "acme/widgets"
        redacted_repo_identifier("acme/secret", is_private=True)    ->  "acme/[redacted:1a2b3c4d]"

    A public repo keeps its full owner and name. A private repo keeps its owner
    scope and swaps the name for a short sha256 prefix of the full name.

    Args:
        full_repo_name: The repo's owner and name, joined by a slash.
        is_private: Whether the repo is private or of unknown visibility.

    Returns:
        The full name for a public repo, or an owner-plus-hash form otherwise.
    """
    if not is_private:
        return full_repo_name
    owner_scope = full_repo_name.split(REPO_FULL_NAME_SEPARATOR)[0]
    full_name_digest = hashlib.sha256(full_repo_name.encode("utf-8")).hexdigest()
    hash_prefix = full_name_digest[:REDACTED_REPO_HASH_PREFIX_LENGTH]
    return REDACTED_REPO_IDENTIFIER_TEMPLATE % (owner_scope, hash_prefix)


def resolve_correlation_floor() -> str:
    """Return the timestamp a listener run must not predate to count for this dispatch.

    ::

        DISPATCHED_AT="2024-04-17T12:00:00Z"  ->  "2024-04-17T12:00:00Z"
        (env unset)                           ->  the report's own start time

    The workflow records the floor just before dispatch. Without it, the
    report's launch time stands in as a close upper bound.

    Returns:
        The correlation-floor timestamp in ISO 8601 form.
    """
    floor_from_environment = os.environ.get(ENV_DISPATCHED_AT, "")
    if floor_from_environment:
        return floor_from_environment
    return datetime.now(timezone.utc).isoformat()


def _run_is_at_or_after_floor(run_created_at: str, dispatched_at_floor: str) -> bool:
    floor_moment = fan_out_dispatch.parse_iso_timestamp(dispatched_at_floor)
    run_moment = fan_out_dispatch.parse_iso_timestamp(run_created_at)
    if floor_moment is None or run_moment is None:
        return False
    return run_moment >= floor_moment


def _fetch_workflow_runs(
    owner: str, repo_name: str, token: str
) -> tuple[int, list[dict[str, object]]]:
    path = LISTENER_RUNS_QUERY_TEMPLATE % (
        owner,
        repo_name,
        fan_out_dispatch.LISTENER_WORKFLOW_FILENAME,
    )
    status_code, runs_payload, _ = fan_out_dispatch.make_github_api_request(path, token)
    if status_code != fan_out_dispatch.HTTP_STATUS_OK or runs_payload is None:
        return status_code, []
    all_workflow_runs = runs_payload.get("workflow_runs")
    if not isinstance(all_workflow_runs, list):
        return status_code, []
    return status_code, all_workflow_runs


def _conclusion_from_most_recent_run(
    all_workflow_runs: list[dict[str, object]],
    dispatched_at_floor: str,
) -> str:
    if not all_workflow_runs:
        return REPORT_STATUS_NO_MATCHING_RUN
    most_recent_run = all_workflow_runs[0]
    run_created_at = str(most_recent_run.get("created_at", ""))
    if not _run_is_at_or_after_floor(run_created_at, dispatched_at_floor):
        return REPORT_STATUS_NO_MATCHING_RUN
    run_conclusion = most_recent_run.get("conclusion")
    if run_conclusion is None:
        return fan_out_dispatch.LISTENER_STATUS_PENDING
    if run_conclusion == fan_out_dispatch.LISTENER_CONCLUSION_SUCCESS:
        return REPORT_STATUS_SUCCEEDED
    return REPORT_STATUS_FAILED


def resolve_dispatch_conclusion(
    owner: str,
    repo_name: str,
    token: str,
    dispatched_at_floor: str,
) -> str:
    """Return this dispatch's listener conclusion for one target repo.

    ::

        404 on the workflow lookup        ->  "listener-missing"
        newest run older than the floor   ->  "no-matching-run"
        matching run still running        ->  "pending"
        matching run concluded success    ->  "succeeded"
        matching run concluded otherwise  ->  "failed"

    Args:
        owner: The target repo's owner login.
        repo_name: The target repo's name.
        token: The installation token for the owner.
        dispatched_at_floor: The ISO timestamp a run must not predate.

    Returns:
        One of the report status labels for this target.
    """
    status_code, all_workflow_runs = _fetch_workflow_runs(owner, repo_name, token)
    if status_code == fan_out_dispatch.HTTP_STATUS_NOT_FOUND:
        return REPORT_STATUS_LISTENER_MISSING
    return _conclusion_from_most_recent_run(all_workflow_runs, dispatched_at_floor)


def _resolve_target_status(
    owner: str,
    repo_name: str,
    token: str,
    dispatched_at_floor: str,
) -> str:
    if fan_out_dispatch.check_opt_out_sentinel(owner, repo_name, token):
        return REPORT_STATUS_OPTED_OUT
    return resolve_dispatch_conclusion(owner, repo_name, token, dispatched_at_floor)


def _report_all_targets(
    all_target_repos: list[dict[str, object]],
    token_by_owner: dict[str, str],
    dispatched_at_floor: str,
) -> None:
    for each_repo in all_target_repos:
        owner_field = each_repo.get("owner")
        owner = owner_field.get("login") if isinstance(owner_field, dict) else None
        repo_name = each_repo.get("name")
        full_repo_name = each_repo.get("full_name")
        if not owner or not repo_name or not full_repo_name:
            continue
        token = token_by_owner.get(str(owner), "")
        is_private = each_repo.get("private") is not False
        status = _resolve_target_status(
            str(owner), str(repo_name), token, dispatched_at_floor
        )
        identifier = redacted_repo_identifier(str(full_repo_name), is_private)
        fan_out_dispatch.dispatch_logger.info(
            REPO_CONCLUSION_LOG_TEMPLATE, identifier, status
        )


def _token_by_owner() -> dict[str, str]:
    return {
        each_owner_scope: os.environ.get(token_env_var_name(each_owner_scope), "")
        for each_owner_scope in fanout_owner_scopes()
    }


def _collect_target_repos(
    token_by_owner: dict[str, str],
) -> list[dict[str, object]]:
    all_target_repos: list[dict[str, object]] = []
    for each_token in token_by_owner.values():
        if not each_token:
            continue
        all_owner_repos = fan_out_dispatch.enumerate_installation_repos(each_token)
        all_target_repos.extend(
            each_repo
            for each_repo in all_owner_repos
            if fan_out_dispatch.is_target_repo(each_repo)
        )
    return all_target_repos


def main() -> int:
    """Report every target's dispatch conclusion, then exit success.

    Returns:
        The process exit code, always zero so the report step never fails the job.
    """
    dispatched_at_floor = resolve_correlation_floor()
    token_by_owner = _token_by_owner()
    all_target_repos = _collect_target_repos(token_by_owner)
    _report_all_targets(all_target_repos, token_by_owner, dispatched_at_floor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
