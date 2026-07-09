"""Specifications for the fan-out dispatch script's pure filtering and formatting logic."""

import os
import subprocess
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import config
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

    def should_include_repos_even_when_permissions_push_is_absent(self) -> None:
        repo = make_repo_fixture("JonEcho/read-only", has_push=False)

        assert fan_out_dispatch.is_target_repo(repo) is True

    def should_include_the_source_repo_for_bugbot_sync(self) -> None:
        repo = make_repo_fixture("jl-cmd/claude-code-config")

        assert fan_out_dispatch.is_target_repo(repo) is True

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
    def should_include_metric_count_header_row(self) -> None:
        table = fan_out_dispatch.build_summary_table({}, {})

        assert "| Metric | Count |" in table
        assert "|--------|-------|" in table

    def should_report_counts_without_repo_names(self) -> None:
        dispatch_status_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            "JonEcho/beta": fan_out_dispatch.DISPATCH_STATUS_OPTED_OUT,
        }

        table = fan_out_dispatch.build_summary_table(dispatch_status_by_repo, {})

        assert "JonEcho/alpha" not in table
        assert "JonEcho/beta" not in table
        assert "| Targets considered | 2 |" in table
        assert "| Dispatch succeeded | 1 |" in table
        assert "| Dispatch opted out | 1 |" in table

    def should_count_listener_conclusions_by_status(self) -> None:
        dispatch_status_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            "JonEcho/beta": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
        }
        conclusion_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.LISTENER_CONCLUSION_SUCCESS,
            "JonEcho/beta": fan_out_dispatch.LISTENER_CONCLUSION_FAILURE,
        }

        table = fan_out_dispatch.build_summary_table(
            dispatch_status_by_repo, conclusion_by_repo
        )

        assert "| Listener success | 1 |" in table
        assert "| Listener failure | 1 |" in table
        assert "JonEcho/alpha" not in table
        assert "JonEcho/beta" not in table

    def should_count_dispatch_failures(self) -> None:
        dispatch_status_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_FAILED,
        }

        table = fan_out_dispatch.build_summary_table(dispatch_status_by_repo, {})

        assert "| Dispatch failed | 1 |" in table


class TestBuildStaleSection:
    def should_return_empty_string_when_no_stale_repos(self) -> None:
        assert fan_out_dispatch.build_stale_section([]) == ""

    def should_report_stale_count_without_repo_names(self) -> None:
        stale_repos = ["JonEcho/old-project", "jl-cmd/abandoned"]

        section = fan_out_dispatch.build_stale_section(stale_repos)

        assert "2 target repo(s)" in section
        assert "JonEcho/old-project" not in section
        assert "jl-cmd/abandoned" not in section

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


class TestScriptEntrypointImportPath:
    def should_load_config_when_run_as_python_script_with_empty_pythonpath(
        self,
        tmp_path: Path,
    ) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        script_path = repo_root / "scripts" / "fan_out_dispatch.py"
        env = os.environ.copy()
        env["PYTHONPATH"] = ""
        env["JONECHO_TOKEN"] = ""
        env["JLCMD_TOKEN"] = ""
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr


class TestImportKeepsAlreadyLoadedConfig:
    def should_leave_an_already_imported_config_module_in_sys_modules(self) -> None:
        fan_out_dispatch._ensure_repo_root_on_sys_path()

        assert sys.modules.get("config") is config


class TestSummaryCountsConclusionsOutsideEnumeratedSet:
    def should_count_conclusions_outside_the_enumerated_status_set(self) -> None:
        dispatch_status_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            "JonEcho/beta": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
        }
        conclusion_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.LISTENER_CONCLUSION_SUCCESS,
            "JonEcho/beta": "cancelled",
        }

        table = fan_out_dispatch.build_summary_table(
            dispatch_status_by_repo, conclusion_by_repo
        )

        assert "| Listener other | 1 |" in table

    def should_reconcile_listener_counts_with_dispatched_repo_total(self) -> None:
        dispatch_status_by_repo = {
            "JonEcho/alpha": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
            "JonEcho/beta": fan_out_dispatch.DISPATCH_STATUS_SUCCEEDED,
        }
        conclusion_by_repo = {
            "JonEcho/alpha": "timed_out",
            "JonEcho/beta": "cancelled",
        }

        metric_rows = fan_out_dispatch._build_summary_metric_rows(
            dispatch_status_by_repo, conclusion_by_repo
        )
        listener_counts = [
            each_count
            for each_label, each_count in metric_rows
            if each_label.startswith("Listener")
        ]

        assert sum(listener_counts) == len(conclusion_by_repo)


class TestMalformedRepoEntriesAreReported:
    def should_warn_with_a_count_when_a_target_entry_is_malformed(self) -> None:
        all_target_repos = [
            {"owner": {"login": "JonEcho"}},
        ]
        token_by_owner = {"JonEcho": FAKE_TOKEN}

        with patch.object(
            fan_out_dispatch.dispatch_logger, "warning"
        ) as mock_warning:
            fan_out_dispatch._dispatch_to_targets(
                all_target_repos, token_by_owner, {}
            )

        malformed_warnings = [
            each_call
            for each_call in mock_warning.call_args_list
            if each_call.args
            and each_call.args[0] == fan_out_dispatch.ACTIONS_MALFORMED_REPO_ENTRY
        ]

        assert malformed_warnings
        assert malformed_warnings[0].args[1] == 1


class TestEnumerationLoggingRoutesThroughDispatchLogger:
    """enumerate_installation_repos must log via dispatch_logger, not print()."""

    def should_log_repository_count_through_the_dispatch_logger(self) -> None:
        one_repo_page = {"repositories": [make_repo_fixture("JonEcho/one")]}
        with patch.object(
            fan_out_dispatch,
            "make_github_api_request",
            return_value=(fan_out_dispatch.HTTP_STATUS_OK, one_repo_page, None),
        ):
            with patch.object(
                fan_out_dispatch.dispatch_logger, "info"
            ) as mock_info:
                all_repos = fan_out_dispatch.enumerate_installation_repos(
                    FAKE_TOKEN
                )

        assert len(all_repos) == 1
        count_logs = [
            each_call
            for each_call in mock_info.call_args_list
            if each_call.args
            and each_call.args[0]
            == fan_out_dispatch.ACTIONS_ENUMERATION_RETURNED_COUNT
        ]
        assert count_logs
        assert count_logs[0].args[1] == 1

    def should_log_http_failure_through_the_dispatch_logger(self) -> None:
        with patch.object(
            fan_out_dispatch,
            "make_github_api_request",
            return_value=(fan_out_dispatch.HTTP_STATUS_FORBIDDEN, None, None),
        ):
            with patch.object(
                fan_out_dispatch.dispatch_logger, "error"
            ) as mock_error:
                all_repos = fan_out_dispatch.enumerate_installation_repos(
                    FAKE_TOKEN
                )

        assert all_repos == []
        http_failure_logs = [
            each_call
            for each_call in mock_error.call_args_list
            if each_call.args
            and each_call.args[0]
            == fan_out_dispatch.ACTIONS_ENUMERATION_HTTP_FAILED
        ]
        assert http_failure_logs
        assert (
            http_failure_logs[0].args[1] == fan_out_dispatch.HTTP_STATUS_FORBIDDEN
        )

    def should_log_network_error_through_the_dispatch_logger(self) -> None:
        with patch.object(
            fan_out_dispatch,
            "make_github_api_request",
            return_value=(fan_out_dispatch.NETWORK_ERROR_STATUS_CODE, None, None),
        ):
            with patch.object(
                fan_out_dispatch.dispatch_logger, "error"
            ) as mock_error:
                all_repos = fan_out_dispatch.enumerate_installation_repos(
                    FAKE_TOKEN
                )

        assert all_repos == []
        network_error_logs = [
            each_call
            for each_call in mock_error.call_args_list
            if each_call.args
            and each_call.args[0]
            == fan_out_dispatch.ACTIONS_ENUMERATION_NETWORK_ERROR
        ]
        assert network_error_logs

    def should_not_embed_actions_annotations_in_the_module_source(self) -> None:
        module_source = Path(fan_out_dispatch.__file__).read_text(
            encoding="utf-8"
        )
        assert "::notice::Enumeration returned" not in module_source
        assert "::error::Enumeration failed" not in module_source
        assert "::error::Network error during enumeration" not in module_source
