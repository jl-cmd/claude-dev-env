import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


def _load_module(module_name: str, filename: str) -> ModuleType:
    module_path = Path(__file__).parent.parent / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(module_name, module)
    spec.loader.exec_module(module)
    return module


post_audit_review = _load_module("post_audit_review", "post_audit_review.py")


class DescribeParseReviewResponse:
    def test_extracts_review_id_and_url_as_two_tuple(self):
        raw = json.dumps({"id": 42, "html_url": "https://github.com/pr#review-42"})
        parsed_review = post_audit_review._parse_review_response(raw)
        assert parsed_review is not None
        review_identifier, review_url = parsed_review
        assert review_identifier == "42"
        assert review_url == "https://github.com/pr#review-42"

    def test_returns_two_tuple_signature_and_ignores_nested_comments(self):
        """The POST /reviews response never echoes inline comments; the third
        tuple element was dead code consumed by `_fetch_inline_review_comments`
        instead. Pin the new 2-tuple shape and confirm a `comments` field in
        the input is silently ignored.
        """
        raw = json.dumps(
            {
                "id": 42,
                "html_url": "https://github.com/pr#review-42",
                "comments": [
                    {"id": 101, "html_url": "https://github.com/pr#comment-101"}
                ],
            }
        )
        parsed_review = post_audit_review._parse_review_response(raw)
        assert parsed_review is not None
        assert len(parsed_review) == 2
        review_identifier, review_url = parsed_review
        assert review_identifier == "42"
        assert review_url == "https://github.com/pr#review-42"

    def test_returns_none_on_invalid_json(self):
        assert post_audit_review._parse_review_response("not json") is None

    def test_returns_none_when_response_is_a_json_array(self):
        raw = json.dumps([{"id": 42, "html_url": "https://github.com/pr"}])
        assert post_audit_review._parse_review_response(raw) is None

    def test_returns_none_when_response_is_a_json_scalar(self):
        raw = json.dumps(42)
        assert post_audit_review._parse_review_response(raw) is None

    def test_returns_none_when_id_missing(self):
        raw = json.dumps({"html_url": "https://github.com/pr"})
        assert post_audit_review._parse_review_response(raw) is None

    def test_returns_none_when_url_not_string(self):
        raw = json.dumps({"id": 1, "html_url": 99})
        assert post_audit_review._parse_review_response(raw) is None

    def test_returns_success_when_post_response_omits_comments_field(self):
        """The GitHub REST API POST /reviews response does NOT include inline
        comments — they are returned via a separate GET /reviews/{id}/comments
        call. Success must therefore be signaled by the review object alone,
        regardless of how many comments were sent in the request payload.
        """
        raw = json.dumps({"id": 42, "html_url": "https://github.com/pr#review-42"})
        parsed_review = post_audit_review._parse_review_response(raw)
        assert parsed_review is not None
        review_identifier, review_url = parsed_review
        assert review_identifier == "42"
        assert review_url == "https://github.com/pr#review-42"


class DescribeBuildOutputPayload:
    def test_builds_correct_json_structure(self):
        output = post_audit_review._build_output_payload(
            "99",
            "https://github.com/pr#review-99",
            [{"id": "101", "url": "https://github.com/pr#comment-101"}],
            fetch_succeeded=True,
        )
        payload = json.loads(output)
        assert payload["review_id"] == "99"
        assert payload["review_url"] == "https://github.com/pr#review-99"
        assert len(payload["comments"]) == 1
        assert payload["comments"][0]["id"] == "101"

    def test_handles_multiple_comments(self):
        output = post_audit_review._build_output_payload(
            "1",
            "url1",
            [{"id": "2", "url": "url2"}, {"id": "3", "url": "url3"}],
            fetch_succeeded=True,
        )
        payload = json.loads(output)
        assert len(payload["comments"]) == 2

    def test_emits_comments_fetch_status_ok_when_fetch_succeeded(self):
        """When the follow-up GET completed successfully (even with zero
        entries), the orchestrator must see status=ok so it can treat the
        zero-comment case as 'review posted with no inline findings' rather
        than 'follow-up GET failed'.
        """
        output = post_audit_review._build_output_payload(
            "1", "url", [], fetch_succeeded=True
        )
        payload = json.loads(output)
        assert payload["comments_fetch_status"] == "ok"

    def test_emits_comments_fetch_status_failed_when_fetch_failed(self):
        """When the follow-up GET itself failed (non-zero gh exit, malformed
        JSON), the orchestrator must see status=failed so it can route fix
        replies against the parent review instead of expecting per-comment
        ids.
        """
        output = post_audit_review._build_output_payload(
            "1", "url", [], fetch_succeeded=False
        )
        payload = json.loads(output)
        assert payload["comments_fetch_status"] == "failed"


def _make_gh_result(
    *, returncode: int, stdout: str, stderr: str = "", is_timed_out: bool = False
) -> object:
    return type(
        "GhResult",
        (),
        {
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "is_timed_out": is_timed_out,
        },
    )()


class DescribePostReview:
    def test_returns_review_info_on_success(self):
        post_response_text = json.dumps(
            {
                "id": 99,
                "html_url": "https://github.com/pr#review-99",
            }
        )
        get_response_text = json.dumps(
            [[{"id": 101, "html_url": "https://github.com/pr#comment-101"}]]
        )
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=post_response_text),
            _make_gh_result(returncode=0, stdout=get_response_text),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ):
            posted_review = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[
                    {"path": "file.py", "line": 42, "side": "RIGHT", "body": "finding"}
                ],
            )
        assert posted_review is not None
        review_id, review_url, all_comment_entries, fetch_succeeded = posted_review
        assert review_id == "99"
        assert review_url == "https://github.com/pr#review-99"
        assert all_comment_entries == [
            {"id": "101", "url": "https://github.com/pr#comment-101"}
        ]
        assert fetch_succeeded is True

    def test_returns_none_on_gh_failure(self):
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=_make_gh_result(
                returncode=1, stdout="", stderr="gh error"
            ),
        ):
            posted_review = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[],
            )
        assert posted_review is None

    def test_fetches_inline_comments_via_followup_get(self):
        post_response_text = json.dumps(
            {"id": 42, "html_url": "https://github.com/pr#review-42"}
        )
        get_response_text = json.dumps(
            [
                [
                    {"id": 201, "html_url": "https://github.com/pr#comment-201"},
                    {"id": 202, "html_url": "https://github.com/pr#comment-202"},
                ]
            ]
        )
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=post_response_text),
            _make_gh_result(returncode=0, stdout=get_response_text),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ):
            posted_review = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[
                    {"path": "file.py", "line": 1, "side": "RIGHT", "body": "f1"},
                    {"path": "file.py", "line": 2, "side": "RIGHT", "body": "f2"},
                ],
            )
        assert posted_review is not None
        _, _, all_comment_entries, fetch_succeeded = posted_review
        assert all_comment_entries == [
            {"id": "201", "url": "https://github.com/pr#comment-201"},
            {"id": "202", "url": "https://github.com/pr#comment-202"},
        ]
        assert fetch_succeeded is True

    def test_followup_get_failure_returns_parent_review_with_empty_comments(self):
        post_response_text = json.dumps(
            {"id": 42, "html_url": "https://github.com/pr#review-42"}
        )
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=post_response_text),
            _make_gh_result(returncode=1, stdout="", stderr="follow-up GET failed"),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ):
            posted_review = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[
                    {"path": "file.py", "line": 1, "side": "RIGHT", "body": "f1"},
                ],
            )
        assert posted_review is not None
        review_id, review_url, all_comment_entries, fetch_succeeded = posted_review
        assert review_id == "42"
        assert review_url == "https://github.com/pr#review-42"
        assert all_comment_entries == []
        assert fetch_succeeded is False

    def test_followup_get_skipped_when_no_comments_were_posted(self):
        post_response_text = json.dumps(
            {"id": 42, "html_url": "https://github.com/pr#review-42"}
        )
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=_make_gh_result(returncode=0, stdout=post_response_text),
        ) as patched_run_gh:
            posted_review = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[],
            )
        assert posted_review is not None
        assert patched_run_gh.call_count == 1


class DescribePostReviewUsesShouldRetryParameterNames:
    """The call to run_gh inside post_review must pass the renamed boolean
    parameters `should_retry_nonzero` and `should_retry_timeout` (CODE_RULES
    §5 boolean prefix).
    """

    def test_post_review_passes_should_retry_kwargs_to_run_gh(self):
        captured_call_kwargs: dict[str, object] = {}

        def fake_run_gh(*_args: object, **kwargs: object) -> object:
            captured_call_kwargs.update(kwargs)
            return type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps({"id": 1, "html_url": "u", "comments": []}),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )()

        with patch.object(post_audit_review, "run_gh", side_effect=fake_run_gh):
            post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="body",
                all_comments=[],
            )
        assert captured_call_kwargs.get("should_retry_nonzero") is False
        assert captured_call_kwargs.get("should_retry_timeout") is False
        assert "retry_nonzero" not in captured_call_kwargs
        assert "retry_timeout" not in captured_call_kwargs


class DescribeParseReviewResponseUsesDomainIdentifiers:
    """Local identifiers in `_parse_review_response` must follow CODE_RULES §5:
    no banned `response` substring — use `parsed_review_object`.
    """

    def test_parse_review_response_uses_domain_identifiers(self):
        parse_review_response_source_text = inspect.getsource(
            post_audit_review._parse_review_response
        )
        assert "parsed_review_object = json.loads(" in parse_review_response_source_text
        assert "response_payload" not in parse_review_response_source_text

    def test_parse_review_response_returns_two_tuple_signature(self):
        """The third tuple element (parsed nested comments) was dead code: the
        POST /reviews response never includes inline comments, and the caller
        discarded the element. Pin the 2-tuple return type.
        """
        parse_review_response_signature = inspect.signature(
            post_audit_review._parse_review_response
        )
        return_annotation_text = str(parse_review_response_signature.return_annotation)
        assert "tuple[str, str]" in return_annotation_text
        assert "list[dict[str, str]]" not in return_annotation_text

    def test_parse_review_response_does_not_parse_nested_comments(self):
        """The dead-code branch reading the (always-empty) `comments` field
        of the POST response must be removed. Inline comments now arrive via
        `_fetch_inline_review_comments`.
        """
        parse_review_response_source_text = inspect.getsource(
            post_audit_review._parse_review_response
        )
        assert "all_nested_comments" not in parse_review_response_source_text
        assert "all_comment_entries" not in parse_review_response_source_text
        assert ".get(\"comments\")" not in parse_review_response_source_text


class DescribeBuildOutputPayloadUsesDomainIdentifier:
    """The local payload variable in `_build_output_payload` must avoid the
    banned word `output` and use the domain-meaningful name
    `review_summary_payload` (CODE_RULES §5 banned-name list).
    """

    def test_build_output_payload_uses_review_summary_payload(self):
        build_output_payload_source_text = inspect.getsource(
            post_audit_review._build_output_payload
        )
        assert (
            "review_summary_payload: dict[str, object] = {"
            in build_output_payload_source_text
        )
        assert "return json.dumps(review_summary_payload)" in build_output_payload_source_text
        assert "output_payload: dict" not in build_output_payload_source_text
        assert "json.dumps(output_payload)" not in build_output_payload_source_text


class DescribeMainUsesDomainIdentifier:
    """The destructured posted-review tuple in `main` must avoid the banned
    word `result` (CODE_RULES §5 banned-name list) and use `posted_review`.
    """

    def test_main_uses_posted_review_identifier(self):
        main_source_text = inspect.getsource(post_audit_review.main)
        assert "posted_review = post_review(" in main_source_text
        assert "if posted_review is None:" in main_source_text
        assert (
            "review_identifier, review_url, all_comment_entries, fetch_succeeded = posted_review"
            in main_source_text
        )
        assert "review_result" not in main_source_text

    def test_main_local_variable_naming_is_pinned(self):
        main_source_text = inspect.getsource(post_audit_review.main)
        assert "serialized_review_summary" in main_source_text
        assert "output_text" not in main_source_text


class DescribeFetchInlineReviewCommentsRetriesEventualConsistency:
    """`_fetch_inline_review_comments` retries the GET with exponential
    backoff when the parsed comment count is below `expected_comment_count`,
    because GitHub's REST API is eventually consistent and may return an
    empty page in a sub-second window after POST creates N comments.
    """

    def test_retries_until_full_count_is_reached(self):
        first_empty = json.dumps([[]])
        second_partial = json.dumps(
            [[{"id": 1, "html_url": "u1"}]]
        )
        third_complete = json.dumps(
            [
                [
                    {"id": 1, "html_url": "u1"},
                    {"id": 2, "html_url": "u2"},
                ]
            ]
        )
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=first_empty),
            _make_gh_result(returncode=0, stdout=second_partial),
            _make_gh_result(returncode=0, stdout=third_complete),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ), patch.object(post_audit_review.time, "sleep"):
            comments_list, fetch_succeeded = (
                post_audit_review._fetch_inline_review_comments(
                    owner="own",
                    repo="rep",
                    pull_number=1,
                    review_identifier="42",
                    expected_comment_count=2,
                )
            )
        assert fetch_succeeded is True
        assert len(comments_list) == 2

    def test_returns_failed_after_all_retries_exhausted_with_partial_count(self):
        """When the retry loop exhausts and the parsed entry count is still
        below `expected_comment_count`, fetch_succeeded must be False so the
        orchestrator can detect the partial state via comments_fetch_status
        and treat the missing finding ids as such. Returning True here causes
        per-finding fix replies for the missing ids to silently fail.
        """
        partial_response = json.dumps([[{"id": 1, "html_url": "u1"}]])
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=partial_response),
            _make_gh_result(returncode=0, stdout=partial_response),
            _make_gh_result(returncode=0, stdout=partial_response),
            _make_gh_result(returncode=0, stdout=partial_response),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ), patch.object(post_audit_review.time, "sleep"):
            comments_list, fetch_succeeded = (
                post_audit_review._fetch_inline_review_comments(
                    owner="own",
                    repo="rep",
                    pull_number=1,
                    review_identifier="42",
                    expected_comment_count=5,
                )
            )
        assert fetch_succeeded is False
        assert len(comments_list) == 1

    def test_returns_failed_when_all_retries_yield_empty(self):
        empty_response = json.dumps([[]])
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=empty_response),
            _make_gh_result(returncode=0, stdout=empty_response),
            _make_gh_result(returncode=0, stdout=empty_response),
            _make_gh_result(returncode=0, stdout=empty_response),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ), patch.object(post_audit_review.time, "sleep"):
            comments_list, fetch_succeeded = (
                post_audit_review._fetch_inline_review_comments(
                    owner="own",
                    repo="rep",
                    pull_number=1,
                    review_identifier="42",
                    expected_comment_count=2,
                )
            )
        assert fetch_succeeded is False
        assert comments_list == []

    def test_returns_failed_on_gh_nonzero_exit(self):
        all_returned_results = [
            _make_gh_result(returncode=1, stdout="", stderr="boom"),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ), patch.object(post_audit_review.time, "sleep"):
            comments_list, fetch_succeeded = (
                post_audit_review._fetch_inline_review_comments(
                    owner="own",
                    repo="rep",
                    pull_number=1,
                    review_identifier="42",
                    expected_comment_count=1,
                )
            )
        assert fetch_succeeded is False
        assert comments_list == []


class DescribeFetchInlineReviewCommentsDropsRedundantRepoFlag:
    """`_fetch_inline_review_comments` must NOT pass `-R owner/repo` to gh
    because the endpoint path itself is `/repos/{owner}/{repo}/...` — the
    repo flag is redundant. Sibling code in `post_review` does not pass the
    flag; consistency matters.
    """

    def test_gh_invocation_excludes_dash_r_flag(self):
        empty_result = _make_gh_result(
            returncode=0,
            stdout=json.dumps([[]]),
            stderr="",
            is_timed_out=False,
        )
        with patch.object(
            post_audit_review, "run_gh", return_value=empty_result
        ) as patched_run_gh, patch.object(post_audit_review.time, "sleep"):
            post_audit_review._fetch_inline_review_comments(
                owner="own",
                repo="rep",
                pull_number=1,
                review_identifier="42",
                expected_comment_count=0,
            )
        assert patched_run_gh.call_count >= 1
        gh_invocation = patched_run_gh.call_args_list[0][0][0]
        assert "-R" not in gh_invocation
        assert "own/rep" not in gh_invocation


class DescribePostReviewThreadsFetchSucceededFlag:
    """`post_review` returns a 4-tuple including a `fetch_succeeded` bool so
    the orchestrator can distinguish 'review posted with zero comments' from
    'review posted but follow-up GET failed'.
    """

    def test_returns_fetch_succeeded_true_when_no_comments_were_posted(self):
        post_response_text = json.dumps(
            {"id": 42, "html_url": "https://github.com/pr#review-42"}
        )
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=_make_gh_result(returncode=0, stdout=post_response_text),
        ):
            posted_review = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[],
            )
        assert posted_review is not None
        _, _, _, fetch_succeeded = posted_review
        assert fetch_succeeded is True


class DescribeMainEmitsCommentsFetchStatusInStdout:
    """The orchestrator parses stdout JSON; the `comments_fetch_status` field
    must surface so per-finding fix routing has a reliable signal.
    """

    def test_main_stdout_contains_comments_fetch_status_field(self):
        post_response_text = json.dumps(
            {"id": 42, "html_url": "https://github.com/pr#review-42"}
        )
        captured_stdout: list[str] = []

        def capture_print(*args, **_kwargs):
            captured_stdout.append(" ".join(str(each_arg) for each_arg in args))

        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=_make_gh_result(returncode=0, stdout=post_response_text),
        ), patch("builtins.print", side_effect=capture_print):
            payload_path = Path(__file__).parent / "_tmp_body.md"
            payload_path.write_text("body", encoding="utf-8")
            try:
                exit_code = post_audit_review.main(
                    [
                        "--owner",
                        "own",
                        "--repo",
                        "rep",
                        "--number",
                        "1",
                        "--commit-id",
                        "abc",
                        "--body-file",
                        str(payload_path),
                    ]
                )
            finally:
                payload_path.unlink(missing_ok=True)
        assert exit_code == 0
        emitted_payload = json.loads(captured_stdout[0])
        assert "comments_fetch_status" in emitted_payload
        assert emitted_payload["comments_fetch_status"] == "ok"


class DescribeParseInlineCommentsResponseDistinguishesPermanentFromTransient:
    """`_parse_inline_comments_response` returns None for permanent failure
    modes (JSON decode failed, root not a list) so the outer retry loop can
    distinguish 'transient under-count, retry warranted' from 'permanent
    parse failure, abort immediately'. A valid empty list still returns [].
    """

    def test_returns_none_on_json_decode_failure(self):
        assert post_audit_review._parse_inline_comments_response("not json") is None

    def test_returns_none_when_root_is_not_a_list(self):
        raw_object = json.dumps({"id": 1, "html_url": "u"})
        assert post_audit_review._parse_inline_comments_response(raw_object) is None

    def test_returns_empty_list_for_valid_empty_pages(self):
        raw_empty = json.dumps([[]])
        assert post_audit_review._parse_inline_comments_response(raw_empty) == []

    def test_returns_parsed_entries_for_valid_response(self):
        raw_response = json.dumps(
            [[{"id": 7, "html_url": "https://x/y#c-7"}]]
        )
        all_entries = post_audit_review._parse_inline_comments_response(raw_response)
        assert all_entries == [{"id": "7", "url": "https://x/y#c-7"}]


class DescribeFetchInlineReviewCommentsAbortsOnPermanentParseFailure:
    """When `_parse_inline_comments_response` returns None (permanent parse
    failure), the retry loop must abort immediately rather than retrying.
    The bool flag is False because no entries were recovered.
    """

    def test_aborts_immediately_when_parse_returns_none(self):
        malformed_response = "not-json-at-all"
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=malformed_response),
            _make_gh_result(returncode=0, stdout=malformed_response),
            _make_gh_result(returncode=0, stdout=malformed_response),
            _make_gh_result(returncode=0, stdout=malformed_response),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ) as patched_run_gh, patch.object(post_audit_review.time, "sleep"):
            comments_list, fetch_succeeded = (
                post_audit_review._fetch_inline_review_comments(
                    owner="own",
                    repo="rep",
                    pull_number=1,
                    review_identifier="42",
                    expected_comment_count=2,
                )
            )
        assert fetch_succeeded is False
        assert comments_list == []
        assert patched_run_gh.call_count == 1

    def test_aborts_immediately_when_root_is_not_a_list(self):
        non_list_root = json.dumps({"unexpected": "shape"})
        all_returned_results = [
            _make_gh_result(returncode=0, stdout=non_list_root),
        ]
        with patch.object(
            post_audit_review, "run_gh", side_effect=all_returned_results
        ) as patched_run_gh, patch.object(post_audit_review.time, "sleep"):
            comments_list, fetch_succeeded = (
                post_audit_review._fetch_inline_review_comments(
                    owner="own",
                    repo="rep",
                    pull_number=1,
                    review_identifier="42",
                    expected_comment_count=1,
                )
            )
        assert fetch_succeeded is False
        assert comments_list == []
        assert patched_run_gh.call_count == 1


class DescribePositiveIntArgparseValidation:
    """`--number` (and `--loop` where applicable) must reject zero and
    negative values at the argparse layer rather than silently producing a
    non-matching header (which masquerades as 'no review found').
    """

    def test_rejects_zero_pull_number(self):
        with patch("sys.stderr"):
            try:
                post_audit_review._parse_arguments(
                    [
                        "--owner",
                        "o",
                        "--repo",
                        "r",
                        "--number",
                        "0",
                        "--commit-id",
                        "c",
                        "--body-file",
                        "b",
                    ]
                )
            except SystemExit as exit_error:
                assert exit_error.code != 0
                return
        assert False, "expected SystemExit for --number 0"

    def test_rejects_negative_pull_number(self):
        with patch("sys.stderr"):
            try:
                post_audit_review._parse_arguments(
                    [
                        "--owner",
                        "o",
                        "--repo",
                        "r",
                        "--number",
                        "-1",
                        "--commit-id",
                        "c",
                        "--body-file",
                        "b",
                    ]
                )
            except SystemExit as exit_error:
                assert exit_error.code != 0
                return
        assert False, "expected SystemExit for --number -1"

    def test_accepts_positive_pull_number(self):
        parsed = post_audit_review._parse_arguments(
            [
                "--owner",
                "o",
                "--repo",
                "r",
                "--number",
                "1",
                "--commit-id",
                "c",
                "--body-file",
                "b",
            ]
        )
        assert parsed.number == 1
