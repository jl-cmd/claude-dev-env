"""Tests for mine_copilot_findings — defect classification and clustering."""

import sys
from pathlib import Path

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from mine_copilot_findings import (  # noqa: E402
    ReviewerComment,
    _pull_number_from_url,
    _reviewer_comment_from_payload,
    classify_defect,
    cluster_defects,
    proposal_for_defect_class,
)
from log_audit_constants.mine_copilot_findings_constants import (  # noqa: E402
    PROPOSAL_BY_DEFECT_CLASS,
)


class TestClassifyDefect:
    def test_recognizes_a_missing_type_hint_comment(self) -> None:
        assert (
            classify_defect("This function is missing a type hint on the return")
            == "missing-type-hint"
        )

    def test_recognizes_a_broad_except_comment(self) -> None:
        assert classify_defect("There is a broad except swallowing errors") == (
            "broad-except"
        )

    def test_recognizes_a_magic_value_comment(self) -> None:
        assert classify_defect("42 is a magic number, extract it") == "magic-value"

    def test_returns_none_for_praise(self) -> None:
        assert classify_defect("Looks great, nicely done!") is None


class TestClusterDefects:
    def test_groups_comments_by_class_and_ranks_by_count(self) -> None:
        comments = [
            ReviewerComment(1, "cursor[bot]", "missing type hint here"),
            ReviewerComment(2, "cursor[bot]", "another missing annotation"),
            ReviewerComment(3, "cursor[bot]", "this is a broad except"),
            ReviewerComment(4, "cursor[bot]", "nice work"),
        ]
        clusters = cluster_defects(comments)
        assert clusters[0].defect_class == "missing-type-hint"
        assert clusters[0].count == 2
        assert len(clusters) == 2

    def test_caps_the_number_of_example_bodies(self) -> None:
        comments = [
            ReviewerComment(each, "cursor[bot]", f"missing type hint number {each}")
            for each in range(10)
        ]
        clusters = cluster_defects(comments)
        assert clusters[0].count == 10
        assert len(clusters[0].example_bodies) == 3


class TestProposalForDefectClass:
    def test_maps_a_class_to_its_skill_edit_proposal(self) -> None:
        proposal = proposal_for_defect_class("broad-except")
        assert proposal.defect_class == "broad-except"
        assert proposal.proposal == PROPOSAL_BY_DEFECT_CLASS["broad-except"]


class TestPullNumberFromUrl:
    def test_reads_the_trailing_pull_number(self) -> None:
        url = "https://api.github.com/repos/owner/name/pulls/867"
        assert _pull_number_from_url(url) == 867

    def test_returns_none_when_the_last_segment_is_not_a_number(self) -> None:
        assert _pull_number_from_url("https://api.github.com/repos/owner/name") is None


class TestReviewerCommentFromPayload:
    def test_builds_a_comment_from_a_reviewer_bot_payload(self) -> None:
        payload = {
            "user": {"login": "cursor[bot]"},
            "body": "missing type hint",
            "pull_request_url": "https://api.github.com/repos/owner/name/pulls/12",
        }
        parsed_comment = _reviewer_comment_from_payload(payload)
        assert parsed_comment == ReviewerComment(
            pull_number=12, author="cursor[bot]", body="missing type hint"
        )

    def test_skips_a_comment_from_a_non_reviewer_login(self) -> None:
        payload = {
            "user": {"login": "some-human"},
            "body": "looks good",
            "pull_request_url": "https://api.github.com/repos/owner/name/pulls/12",
        }
        assert _reviewer_comment_from_payload(payload) is None

    def test_skips_a_payload_that_is_not_a_dict(self) -> None:
        assert _reviewer_comment_from_payload("not a payload") is None

    def test_skips_a_payload_missing_the_pull_request_url(self) -> None:
        payload = {"user": {"login": "cursor[bot]"}, "body": "missing type hint"}
        assert _reviewer_comment_from_payload(payload) is None

    def test_skips_a_payload_whose_url_has_no_numeric_pull_number(self) -> None:
        payload = {
            "user": {"login": "cursor[bot]"},
            "body": "missing type hint",
            "pull_request_url": "https://api.github.com/repos/owner/name/pulls",
        }
        assert _reviewer_comment_from_payload(payload) is None
