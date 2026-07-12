"""Specifications for the fan-out conclusion report's redaction and correlation logic."""

import os
from unittest.mock import patch

import fan_out_conclusion_report
import fan_out_dispatch

INSTALLATION_STANDIN = "placeholder-installation"
EXAMPLE_OWNER = "example-owner"
EXAMPLE_REPO = "example-repo"
DISPATCH_FLOOR = "2024-04-17T12:00:00+00:00"
RUN_AFTER_FLOOR = "2024-04-17T12:30:00Z"
RUN_BEFORE_FLOOR = "2024-04-17T11:00:00Z"


def _one_run(created_at: str, conclusion: str) -> dict:
    return {"created_at": created_at, "conclusion": conclusion}


def _conclusion_for_runs(status_code: int, all_workflow_runs: list) -> str:
    runs_payload = {"workflow_runs": all_workflow_runs}
    with patch.object(
        fan_out_dispatch,
        "make_github_api_request",
        return_value=(status_code, runs_payload, None),
    ):
        return fan_out_conclusion_report.resolve_dispatch_conclusion(
            EXAMPLE_OWNER, EXAMPLE_REPO, INSTALLATION_STANDIN, DISPATCH_FLOOR
        )


def _conclusion_for_missing_workflow() -> str:
    with patch.object(
        fan_out_dispatch,
        "make_github_api_request",
        return_value=(fan_out_dispatch.HTTP_STATUS_NOT_FOUND, None, None),
    ):
        return fan_out_conclusion_report.resolve_dispatch_conclusion(
            EXAMPLE_OWNER, EXAMPLE_REPO, INSTALLATION_STANDIN, DISPATCH_FLOOR
        )


def _logged_identifier_for(target_repo: dict) -> str:
    token_by_owner = {EXAMPLE_OWNER: INSTALLATION_STANDIN}
    with patch.object(
        fan_out_dispatch,
        "make_github_api_request",
        return_value=(fan_out_dispatch.HTTP_STATUS_NOT_FOUND, None, None),
    ), patch.object(fan_out_dispatch, "dispatch_logger") as recording_logger:
        fan_out_conclusion_report._report_all_targets(
            [target_repo], token_by_owner, DISPATCH_FLOOR
        )
    return recording_logger.info.call_args.args[1]


class TestRedactedRepoIdentifier:
    def should_return_full_name_for_public_target(self) -> None:
        identifier = fan_out_conclusion_report.redacted_repo_identifier(
            "example-owner/public-repo", is_private=False
        )

        assert identifier == "example-owner/public-repo"

    def should_hide_private_target_name_but_keep_owner(self) -> None:
        identifier = fan_out_conclusion_report.redacted_repo_identifier(
            "example-owner/secret-repo", is_private=True
        )

        assert identifier.startswith("example-owner/")
        assert "secret-repo" not in identifier

    def should_produce_a_stable_hash_prefix(self) -> None:
        first_identifier = fan_out_conclusion_report.redacted_repo_identifier(
            "example-owner/secret-repo", is_private=True
        )
        second_identifier = fan_out_conclusion_report.redacted_repo_identifier(
            "example-owner/secret-repo", is_private=True
        )

        assert first_identifier == second_identifier

    def should_use_the_configured_hash_prefix_length(self) -> None:
        identifier = fan_out_conclusion_report.redacted_repo_identifier(
            "example-owner/secret-repo", is_private=True
        )
        hash_prefix = identifier.rsplit(":", 1)[1].rstrip("]")

        assert (
            len(hash_prefix)
            == fan_out_conclusion_report.REDACTED_REPO_HASH_PREFIX_LENGTH
        )

    def should_differ_between_distinct_private_targets(self) -> None:
        first_identifier = fan_out_conclusion_report.redacted_repo_identifier(
            "example-owner/repo-one", is_private=True
        )
        second_identifier = fan_out_conclusion_report.redacted_repo_identifier(
            "example-owner/repo-two", is_private=True
        )

        assert first_identifier != second_identifier


class TestResolveCorrelationFloor:
    def should_use_dispatched_at_env_as_the_floor(self) -> None:
        with patch.dict(os.environ, {"DISPATCHED_AT": DISPATCH_FLOOR}, clear=False):
            floor = fan_out_conclusion_report.resolve_correlation_floor()

        assert floor == DISPATCH_FLOOR

    def should_fall_back_to_a_parseable_timestamp_when_env_unset(self) -> None:
        with patch.dict(os.environ, {"DISPATCHED_AT": ""}, clear=False):
            floor = fan_out_conclusion_report.resolve_correlation_floor()

        assert fan_out_dispatch.parse_iso_timestamp(floor) is not None


class TestResolveDispatchConclusion:
    def should_report_listener_missing_on_workflow_not_found(self) -> None:
        status = _conclusion_for_missing_workflow()

        assert status == fan_out_conclusion_report.REPORT_STATUS_LISTENER_MISSING

    def should_report_succeeded_for_a_matching_successful_run(self) -> None:
        status = _conclusion_for_runs(
            fan_out_dispatch.HTTP_STATUS_OK,
            [_one_run(RUN_AFTER_FLOOR, "success")],
        )

        assert status == fan_out_conclusion_report.REPORT_STATUS_SUCCEEDED

    def should_report_failed_for_a_matching_unsuccessful_run(self) -> None:
        status = _conclusion_for_runs(
            fan_out_dispatch.HTTP_STATUS_OK,
            [_one_run(RUN_AFTER_FLOOR, "failure")],
        )

        assert status == fan_out_conclusion_report.REPORT_STATUS_FAILED

    def should_not_attribute_a_run_that_predates_the_floor(self) -> None:
        status = _conclusion_for_runs(
            fan_out_dispatch.HTTP_STATUS_OK,
            [_one_run(RUN_BEFORE_FLOOR, "success")],
        )

        assert status == fan_out_conclusion_report.REPORT_STATUS_NO_MATCHING_RUN

    def should_report_no_matching_run_when_no_runs_exist(self) -> None:
        status = _conclusion_for_runs(fan_out_dispatch.HTTP_STATUS_OK, [])

        assert status == fan_out_conclusion_report.REPORT_STATUS_NO_MATCHING_RUN

    def should_report_no_matching_run_on_a_server_error(self) -> None:
        status = _conclusion_for_runs(
            fan_out_dispatch.HTTP_STATUS_FORBIDDEN,
            [_one_run(RUN_AFTER_FLOOR, "success")],
        )

        assert status == fan_out_conclusion_report.REPORT_STATUS_NO_MATCHING_RUN

    def should_report_pending_for_a_matching_run_without_a_conclusion(self) -> None:
        status = _conclusion_for_runs(
            fan_out_dispatch.HTTP_STATUS_OK,
            [{"created_at": RUN_AFTER_FLOOR, "conclusion": None}],
        )

        assert status == fan_out_dispatch.LISTENER_STATUS_PENDING


class TestResolveTargetStatus:
    def should_report_opted_out_when_the_target_carries_an_opt_out_sentinel(
        self,
    ) -> None:
        with patch.object(
            fan_out_dispatch, "check_opt_out_sentinel", return_value=True
        ):
            status = fan_out_conclusion_report._resolve_target_status(
                EXAMPLE_OWNER, EXAMPLE_REPO, INSTALLATION_STANDIN, DISPATCH_FLOOR
            )

        assert status == fan_out_conclusion_report.REPORT_STATUS_OPTED_OUT


class TestReportAllTargets:
    def should_redact_a_target_whose_visibility_is_unknown(self) -> None:
        target_missing_private_key = {
            "owner": {"login": EXAMPLE_OWNER},
            "name": "secret-repo",
            "full_name": "example-owner/secret-repo",
        }

        logged_identifier = _logged_identifier_for(target_missing_private_key)

        assert logged_identifier.startswith("example-owner/")
        assert "secret-repo" not in logged_identifier
