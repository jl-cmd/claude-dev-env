"""Tests for mine_copilot_findings — defect classification and clustering."""

import sys
from pathlib import Path

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from mine_copilot_findings import (  # noqa: E402
    ReviewerComment,
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
