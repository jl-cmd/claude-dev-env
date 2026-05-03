"""Tests for pr_converge_constants.

Verifies that path templates accept the documented format substitutions
(owner, repo, number, comment_id) and the bugbot regex matches dirty review
bodies but not clean ones.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "pr_converge_constants.py"
    spec = importlib.util.spec_from_file_location("pr_converge_constants", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pr_converge_constants_module = _load_module()


def test_reviews_path_template_accepts_owner_repo_number() -> None:
    rendered = pr_converge_constants_module.GH_REVIEWS_PATH_TEMPLATE.format(
        owner="acme", repo="widget", number=42
    )
    assert rendered == "repos/acme/widget/pulls/42/reviews?per_page=100"


def test_inline_comments_path_template_accepts_owner_repo_number() -> None:
    rendered = pr_converge_constants_module.GH_INLINE_COMMENTS_PATH_TEMPLATE.format(
        owner="acme", repo="widget", number=42
    )
    assert rendered == "repos/acme/widget/pulls/42/comments?per_page=100"


def test_pr_object_path_template_accepts_owner_repo_number() -> None:
    rendered = pr_converge_constants_module.GH_PR_OBJECT_PATH_TEMPLATE.format(
        owner="acme", repo="widget", number=42
    )
    assert rendered == "repos/acme/widget/pulls/42"


def test_inline_comment_reply_path_template_accepts_all_substitutions() -> None:
    rendered = (
        pr_converge_constants_module.GH_INLINE_COMMENT_REPLY_PATH_TEMPLATE.format(
            owner="acme", repo="widget", number=42, comment_id=12345
        )
    )
    assert rendered == "repos/acme/widget/pulls/42/comments/12345/replies"


def test_bugbot_dirty_body_regex_distinguishes_findings_from_clean_bodies() -> None:
    dirty_body = "Cursor Bugbot has reviewed your changes and found 3 potential issues."
    clean_body = "Bugbot reviewed your changes and found no new issues!"
    compiled_pattern = re.compile(pr_converge_constants_module.BUGBOT_DIRTY_BODY_REGEX)
    dirty_match = compiled_pattern.search(dirty_body)
    assert dirty_match is not None
    assert "found 3 potential issue" in dirty_match.group(0)
    assert compiled_pattern.search(clean_body) is None


def test_cursor_bot_login_matches_github_login_string() -> None:
    assert pr_converge_constants_module.CURSOR_BOT_LOGIN == "cursor[bot]"


def test_bugbot_run_trigger_phrase_ends_with_newline() -> None:
    assert pr_converge_constants_module.BUGBOT_RUN_TRIGGER_PHRASE == "bugbot run\n"


def test_pr_context_fields_lists_documented_field_names() -> None:
    fields_arg = pr_converge_constants_module.PR_CONTEXT_FIELDS
    for required_field in (
        "number",
        "url",
        "headRefOid",
        "baseRefName",
        "headRefName",
        "isDraft",
    ):
        assert required_field in fields_arg


def test_gh_field_body_at_prefix_matches_gh_field_from_file_form() -> None:
    assert pr_converge_constants_module.GH_FIELD_BODY_AT_PREFIX == "body=@"


def test_gh_repo_arg_template_renders_owner_slash_repo() -> None:
    rendered = pr_converge_constants_module.GH_REPO_ARG_TEMPLATE.format(
        owner="acme", repo="widget"
    )
    assert rendered == "acme/widget"


def test_copilot_reviewer_login_carries_bot_suffix() -> None:
    assert (
        pr_converge_constants_module.COPILOT_REVIEWER_LOGIN
        == "copilot-pull-request-reviewer[bot]"
    )


def test_copilot_reviewer_request_id_reuses_login_constant() -> None:
    request_id = pr_converge_constants_module.COPILOT_REVIEWER_REQUEST_ID
    login = pr_converge_constants_module.COPILOT_REVIEWER_LOGIN
    assert request_id == login
    assert request_id is login


def test_copilot_clean_review_state_is_approved() -> None:
    assert pr_converge_constants_module.COPILOT_CLEAN_REVIEW_STATE == "APPROVED"


def test_copilot_dirty_review_states_lists_changes_requested_and_commented() -> None:
    dirty_states = pr_converge_constants_module.ALL_COPILOT_DIRTY_REVIEW_STATES
    assert "CHANGES_REQUESTED" in dirty_states
    assert "COMMENTED" in dirty_states


def test_copilot_soft_dirty_review_state_is_commented() -> None:
    assert pr_converge_constants_module.COPILOT_SOFT_DIRTY_REVIEW_STATE == "COMMENTED"


def test_mergeability_fields_lists_required_field_names() -> None:
    fields_arg = pr_converge_constants_module.MERGEABILITY_FIELDS
    for required_field in ("mergeable", "mergeStateStatus", "headRefOid"):
        assert required_field in fields_arg


def test_requested_reviewers_path_template_accepts_owner_repo_number() -> None:
    rendered = (
        pr_converge_constants_module.GH_REQUESTED_REVIEWERS_PATH_TEMPLATE.format(
            owner="acme", repo="widget", number=42
        )
    )
    assert rendered == "repos/acme/widget/pulls/42/requested_reviewers"


def test_requested_reviewers_field_template_accepts_reviewer_id() -> None:
    rendered = (
        pr_converge_constants_module.GH_REQUESTED_REVIEWERS_FIELD_TEMPLATE.format(
            reviewer_id="copilot-pull-request-reviewer[bot]"
        )
    )
    assert rendered == "reviewers[]=copilot-pull-request-reviewer[bot]"


def test_pr_base_ref_fields_lists_base_ref_name() -> None:
    assert "baseRefName" in pr_converge_constants_module.PR_BASE_REF_FIELDS


def test_copilot_followup_branch_template_renders_parent_number_and_sha() -> None:
    rendered = (
        pr_converge_constants_module.COPILOT_FOLLOWUP_BRANCH_TEMPLATE.format(
            parent_number=312, short_sha="abc12345"
        )
    )
    assert rendered == "chore/copilot-followup-312-abc12345"


def test_copilot_followup_pr_title_template_renders_parent_number() -> None:
    rendered = (
        pr_converge_constants_module.COPILOT_FOLLOWUP_PR_TITLE_TEMPLATE.format(
            parent_number=312
        )
    )
    assert rendered == "chore: address Copilot findings from PR #312"


def test_copilot_followup_short_sha_length_is_eight() -> None:
    assert pr_converge_constants_module.COPILOT_FOLLOWUP_SHORT_SHA_LENGTH == 8
