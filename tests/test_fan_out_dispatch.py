"""Specifications for the fan-out dispatch script's pure filtering and formatting logic."""

import os
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import fan_out_dispatch


def make_repo_fixture(
    full_name: str = "JonEcho/some-repo",
    archived: bool = False,
    has_push: bool = True,
    is_fork: bool = False,
) -> dict:
    owner_login = full_name.split("/")[0]
    return {
        "full_name": full_name,
        "name": full_name.split("/")[1],
        "owner": {"login": owner_login},
        "archived": archived,
        "fork": is_fork,
        "permissions": {"push": has_push, "pull": True},
    }


class TestIsTargetRepo:
    def should_include_jonecho_repos_with_push(self) -> None:
        repo = make_repo_fixture("JonEcho/my-project")

        assert fan_out_dispatch.is_target_repo(repo) is True

    def should_include_jlcmd_repos_with_push(self) -> None:
        repo = make_repo_fixture("jl-cmd/some-tool")

        assert fan_out_dispatch.is_target_repo(repo) is True

    def should_exclude_archived_repos(self) -> None:
        repo = make_repo_fixture("JonEcho/old-project", archived=True)

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_exclude_repos_without_push_permission(self) -> None:
        repo = make_repo_fixture("JonEcho/read-only", has_push=False)

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_exclude_the_source_repo_itself(self) -> None:
        repo = make_repo_fixture("jl-cmd/claude-code-config")

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_exclude_repos_owned_by_other_accounts(self) -> None:
        repo = make_repo_fixture("some-other-org/their-project")

        assert fan_out_dispatch.is_target_repo(repo) is False

    def should_include_forks_when_owner_is_jonecho(self) -> None:
        repo = make_repo_fixture("JonEcho/forked-repo", is_fork=True)

        assert fan_out_dispatch.is_target_repo(repo) is True

    def should_include_forks_when_owner_is_jlcmd(self) -> None:
        repo = make_repo_fixture("jl-cmd/forked-repo", is_fork=True)

        assert fan_out_dispatch.is_target_repo(repo) is True


class TestBuildSummaryTable:
    def should_include_header_row(self) -> None:
        table = fan_out_dispatch.build_summary_table({}, {}, {})

        assert "| Repo |" in table
        assert "| Dispatch Status |" in table
        assert "| Listener Conclusion |" in table

    def should_list_each_repo_in_its_own_row(self) -> None:
        dispatch_status_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            "JonEcho/beta": "opted-out",
        }

        table = fan_out_dispatch.build_summary_table(dispatch_status_by_repo, {}, {})

        assert "JonEcho/alpha" in table
        assert "JonEcho/beta" in table

    def should_show_listener_conclusion_alongside_dispatch_status(self) -> None:
        dispatch_status_by_repo = {"JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED}
        conclusion_by_repo = {"JonEcho/alpha": "success"}

        table = fan_out_dispatch.build_summary_table(
            dispatch_status_by_repo, conclusion_by_repo, {}
        )

        assert "success" in table

    def should_show_notes_when_provided(self) -> None:
        dispatch_status_by_repo = {"JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED}
        notes_by_repo = {"JonEcho/alpha": "drift or sync error"}

        table = fan_out_dispatch.build_summary_table(
            dispatch_status_by_repo, {}, notes_by_repo
        )

        assert "drift or sync error" in table


class TestBuildStaleSection:
    def should_return_empty_string_when_no_stale_repos(self) -> None:
        assert fan_out_dispatch.build_stale_section([]) == ""

    def should_list_each_stale_repo(self) -> None:
        stale_repos = ["JonEcho/old-project", "jl-cmd/abandoned"]

        section = fan_out_dispatch.build_stale_section(stale_repos)

        assert "JonEcho/old-project" in section
        assert "jl-cmd/abandoned" in section

    def should_include_stale_section_heading(self) -> None:
        section = fan_out_dispatch.build_stale_section(["JonEcho/some-repo"])

        assert "Stale listeners" in section


FAKE_TOKEN = "ghs_fake_installation_token"
FAKE_OWNER = "JonEcho"
FAKE_REPO = "some-repo"
DISPATCHED_AT_EARLY = "2024-04-17T12:00:00+00:00"
RUN_CREATED_AT_LATER = "2024-04-17T12:30:00Z"
HTTP_STATUS_INTERNAL_SERVER_ERROR = 500


class TestPollListenerSurfacesPollError:
    """Non-404 HTTP errors on the poll call must surface as LISTENER_STATUS_POLL_ERROR."""

    def should_return_poll_error_when_github_returns_server_error(self) -> None:
        with patch.object(
            fan_out_dispatch,
            "make_github_api_request",
            return_value=(HTTP_STATUS_INTERNAL_SERVER_ERROR, None, None),
        ):
            conclusion = fan_out_dispatch.poll_listener_run_conclusion(
                FAKE_OWNER, FAKE_REPO, FAKE_TOKEN, DISPATCHED_AT_EARLY
            )

        assert conclusion == fan_out_dispatch.LISTENER_STATUS_POLL_ERROR

    def should_return_missing_only_when_github_returns_not_found(self) -> None:
        with patch.object(
            fan_out_dispatch,
            "make_github_api_request",
            return_value=(fan_out_dispatch.HTTP_STATUS_NOT_FOUND, None, None),
        ):
            conclusion = fan_out_dispatch.poll_listener_run_conclusion(
                FAKE_OWNER, FAKE_REPO, FAKE_TOKEN, DISPATCHED_AT_EARLY
            )

        assert conclusion == fan_out_dispatch.LISTENER_STATUS_MISSING


class TestExitCodeFailsOnListenerProblems:
    """Exit code must reflect dispatch failures and listener-side problems."""

    def should_exit_zero_when_every_dispatch_succeeded_and_every_conclusion_succeeded(
        self,
    ) -> None:
        exit_code = fan_out_dispatch.compute_exit_code(
            dispatch_status_by_repo={
                "jl-cmd/one": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
                "jl-cmd/two": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            },
            conclusion_by_repo={
                "jl-cmd/one": fan_out_dispatch.LISTENER_CONCLUSION_SUCCESS,
                "jl-cmd/two": fan_out_dispatch.LISTENER_CONCLUSION_SUCCESS,
            },
        )

        assert exit_code == 0

    def should_exit_nonzero_when_any_dispatch_failed(self) -> None:
        exit_code = fan_out_dispatch.compute_exit_code(
            dispatch_status_by_repo={
                "jl-cmd/one": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
                "jl-cmd/two": fan_out_dispatch.DISPATCH_STATUS_FAILED,
            },
            conclusion_by_repo={
                "jl-cmd/one": fan_out_dispatch.LISTENER_CONCLUSION_SUCCESS,
            },
        )

        assert exit_code == 1

    def should_exit_nonzero_when_any_listener_conclusion_failed(self) -> None:
        exit_code = fan_out_dispatch.compute_exit_code(
            dispatch_status_by_repo={
                "jl-cmd/one": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            },
            conclusion_by_repo={
                "jl-cmd/one": fan_out_dispatch.LISTENER_CONCLUSION_FAILURE,
            },
        )

        assert exit_code == 1

    def should_exit_nonzero_when_any_listener_conclusion_is_pending(self) -> None:
        exit_code = fan_out_dispatch.compute_exit_code(
            dispatch_status_by_repo={
                "jl-cmd/one": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            },
            conclusion_by_repo={
                "jl-cmd/one": fan_out_dispatch.LISTENER_STATUS_PENDING,
            },
        )

        assert exit_code == 1

    def should_exit_nonzero_when_any_listener_conclusion_is_poll_error(self) -> None:
        exit_code = fan_out_dispatch.compute_exit_code(
            dispatch_status_by_repo={
                "jl-cmd/one": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            },
            conclusion_by_repo={
                "jl-cmd/one": fan_out_dispatch.LISTENER_STATUS_POLL_ERROR,
            },
        )

        assert exit_code == 1


class TestTimestampComparisonUsesDatetimeParse:
    """Timestamps with Z suffix and microsecond offsets must compare numerically."""

    def should_parse_z_terminated_iso_timestamp_to_utc_datetime(self) -> None:
        parsed = fan_out_dispatch.parse_iso_timestamp("2024-04-17T12:30:00Z")

        assert parsed is not None
        assert parsed == datetime(2024, 4, 17, 12, 30, 0, tzinfo=timezone.utc)

    def should_parse_offset_iso_timestamp_to_datetime(self) -> None:
        parsed = fan_out_dispatch.parse_iso_timestamp("2024-04-17T12:30:00.123456+00:00")

        assert parsed is not None
        assert parsed.year == 2024
        assert parsed.microsecond == 123456

    def should_return_none_for_unparseable_text(self) -> None:
        parsed = fan_out_dispatch.parse_iso_timestamp("")

        assert parsed is None

    def should_rank_z_terminated_run_as_later_than_microsecond_offset_dispatch(
        self,
    ) -> None:
        dispatch_moment = fan_out_dispatch.parse_iso_timestamp(
            "2024-04-17T12:30:00.000000+00:00"
        )
        run_moment = fan_out_dispatch.parse_iso_timestamp("2024-04-17T12:30:01Z")

        assert dispatch_moment is not None
        assert run_moment is not None
        assert run_moment >= dispatch_moment


class TestSourceCommitEmptyFallback:
    """Empty SOURCE_COMMIT env var falls back to UNKNOWN_COMMIT_PLACEHOLDER."""

    def should_treat_empty_source_commit_as_unknown_placeholder(self) -> None:
        with patch.dict(os.environ, {"SOURCE_COMMIT": ""}, clear=False):
            resolved = fan_out_dispatch.resolve_source_commit_from_environment()

        assert resolved == fan_out_dispatch.UNKNOWN_COMMIT_PLACEHOLDER

    def should_preserve_non_empty_source_commit_value(self) -> None:
        with patch.dict(
            os.environ, {"SOURCE_COMMIT": "abc1234deadbeef"}, clear=False
        ):
            resolved = fan_out_dispatch.resolve_source_commit_from_environment()

        assert resolved == "abc1234deadbeef"


RUN_CREATED_AT_FUTURE = "2099-04-17T12:30:01Z"


def make_http_error(
    retry_after_header_value: str,
) -> urllib.error.HTTPError:
    headers = Message()
    headers["Retry-After"] = retry_after_header_value
    return urllib.error.HTTPError(
        url="https://api.github.com/fake",
        code=fan_out_dispatch.HTTP_STATUS_TOO_MANY_REQUESTS,
        msg="Too Many Requests",
        hdrs=headers,
        fp=BytesIO(b""),
    )


class TestRetryAfterHttpDateParsing:
    """Retry-After may arrive as an integer of seconds or as an HTTP-date string."""

    def should_return_integer_seconds_when_header_is_numeric(self) -> None:
        http_error = make_http_error("30")

        with patch("urllib.request.urlopen", side_effect=http_error):
            status_code, _, retry_after_seconds = fan_out_dispatch.make_github_api_request(
                "/fake", "token"
            )

        assert status_code == fan_out_dispatch.HTTP_STATUS_TOO_MANY_REQUESTS
        assert retry_after_seconds == 30

    def should_return_positive_delta_when_header_is_http_date(self) -> None:
        future_moment = datetime.now(timezone.utc) + timedelta(seconds=120)
        http_date_text = format_datetime(future_moment, usegmt=True)
        http_error = make_http_error(http_date_text)

        with patch("urllib.request.urlopen", side_effect=http_error):
            _, _, retry_after_seconds = fan_out_dispatch.make_github_api_request(
                "/fake", "token"
            )

        assert retry_after_seconds is not None
        assert retry_after_seconds > 0
        assert retry_after_seconds <= 120

    def should_return_none_when_header_is_unparseable(self) -> None:
        http_error = make_http_error("not-a-date-or-number")

        with patch("urllib.request.urlopen", side_effect=http_error):
            _, _, retry_after_seconds = fan_out_dispatch.make_github_api_request(
                "/fake", "token"
            )

        assert retry_after_seconds is None


class TestPollListenerRetriesUntilWorkflowRunAppears:
    """The poll loop retries across empty workflow_runs lists up to the cap."""

    def should_return_missing_after_all_attempts_when_workflow_runs_stay_empty(
        self,
    ) -> None:
        with patch.object(
            fan_out_dispatch,
            "make_github_api_request",
            return_value=(fan_out_dispatch.HTTP_STATUS_OK, {"workflow_runs": []}, None),
        ) as mock_request:
            with patch.object(fan_out_dispatch.time, "sleep"):
                conclusion = fan_out_dispatch.poll_listener_run_conclusion(
                    FAKE_OWNER, FAKE_REPO, FAKE_TOKEN, DISPATCHED_AT_EARLY
                )

        assert conclusion == fan_out_dispatch.LISTENER_STATUS_MISSING
        assert mock_request.call_count == fan_out_dispatch.LISTENER_POLL_MAX_ATTEMPTS

    def should_return_conclusion_when_workflow_run_appears_on_later_attempt(
        self,
    ) -> None:
        empty_response = (
            fan_out_dispatch.HTTP_STATUS_OK,
            {"workflow_runs": []},
            None,
        )
        populated_response = (
            fan_out_dispatch.HTTP_STATUS_OK,
            {
                "workflow_runs": [
                    {
                        "created_at": RUN_CREATED_AT_FUTURE,
                        "conclusion": "success",
                    }
                ]
            },
            None,
        )
        with patch.object(
            fan_out_dispatch,
            "make_github_api_request",
            side_effect=[empty_response, empty_response, populated_response],
        ):
            with patch.object(fan_out_dispatch.time, "sleep"):
                conclusion = fan_out_dispatch.poll_listener_run_conclusion(
                    FAKE_OWNER, FAKE_REPO, FAKE_TOKEN, DISPATCHED_AT_EARLY
                )

        assert conclusion == "success"
