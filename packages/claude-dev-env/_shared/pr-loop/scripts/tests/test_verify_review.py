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


verify_review = _load_module("verify_review", "verify_review.py")


class DescribeBuildReviewsApiPath:
    def test_formats_owner_repo_number_into_api_path(self):
        path = verify_review._build_reviews_api_path("own", "rep", 42)
        assert "own" in path
        assert "rep" in path
        assert "42" in path
        assert path.startswith("/repos/")

    def test_returns_exact_paginated_reviews_path_for_owner_repo_number(self):
        api_path = verify_review._build_reviews_api_path("owner", "repo", 42)
        assert api_path == "/repos/owner/repo/pulls/42/reviews?per_page=100"


class DescribeBuildExpectedHeaders:
    def test_returns_both_header_variants_for_loop_3(self):
        loop_audit, bugteam_loop = verify_review._build_expected_headers(3)
        assert "3" in loop_audit
        assert "3" in bugteam_loop
        assert loop_audit.startswith("## Loop ")
        assert bugteam_loop.startswith("## /bugteam loop ")


class DescribeIsMatchingReview:
    def test_matches_loop_audit_header(self):
        headers = ("## Loop 3 Audit", "## /bugteam loop 3")
        assert verify_review._is_matching_review(
            "## Loop 3 Audit - Merged Findings", headers
        )

    def test_matches_bugteam_loop_header(self):
        all_expected_headers = verify_review._build_expected_headers(1)
        bugteam_loop_header = all_expected_headers[1]
        assert verify_review._is_matching_review(bugteam_loop_header, all_expected_headers)

    def test_rejects_unrelated_body(self):
        headers = ("## Loop 2 Audit", "## /bugteam loop 2")
        assert not verify_review._is_matching_review("## Pull request overview", headers)

    def test_treats_none_body_as_empty(self):
        headers = ("## Loop 1 Audit", "## /bugteam loop 1")
        assert not verify_review._is_matching_review(None, headers)


class DescribeParsePaginatedSlurpResponse:
    def test_flattens_array_of_pages(self):
        raw = json.dumps([[{"a": 1}], [{"b": 2}, {"c": 3}]])
        result = verify_review._parse_paginated_slurp_response(raw)
        assert result == [{"a": 1}, {"b": 2}, {"c": 3}]

    def test_returns_none_for_invalid_json(self):
        assert verify_review._parse_paginated_slurp_response("not json") is None

    def test_returns_none_when_root_is_not_list(self):
        assert verify_review._parse_paginated_slurp_response('"string"') is None

    def test_returns_none_when_page_is_not_list(self):
        raw = json.dumps([[{"a": 1}], "not-a-page"])
        assert verify_review._parse_paginated_slurp_response(raw) is None

    def test_returns_none_when_item_is_not_dict(self):
        raw = json.dumps([[{"a": 1}, 42]])
        assert verify_review._parse_paginated_slurp_response(raw) is None


class DescribeVerifyPrReview:
    def test_returns_exit_ok_when_exactly_one_review_matches(self):
        sample_review = {
            "id": 99,
            "body": "## Loop 3 Audit - Merged Findings",
            "commit_id": "abc1234",
            "html_url": "https://github.com/own/rep/pull/1#review-99",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[sample_review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == 0

    def test_returns_exit_no_review_when_no_matching_loop_header(self):
        wrong_review = {
            "id": 1,
            "body": "## Pull request overview",
            "commit_id": "abc1234",
            "html_url": "url",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[wrong_review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == 1

    def test_returns_exit_wrong_commit_when_commit_id_differs(self):
        review = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": "wrong99",
            "html_url": "url",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == 2

    def test_returns_exit_duplicate_when_multiple_matching_reviews_across_commits(self):
        first_stale = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": "stale_one",
            "html_url": "url-1",
        }
        second_stale = {
            "id": 2,
            "body": "## /bugteam loop 3 ",
            "commit_id": "stale_two",
            "html_url": "url-2",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[first_stale, second_stale]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review(
                "own", "rep", 1, "expected_sha", 3
            )
        assert exit_code == verify_review.EXIT_DUPLICATE_REVIEW

    def test_returns_exit_duplicate_when_mixed_expected_and_stale_matching_reviews(self):
        expected_review = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": "expected_sha",
            "html_url": "url-1",
        }
        stale_review = {
            "id": 2,
            "body": "## /bugteam loop 3 ",
            "commit_id": "stale_sha",
            "html_url": "url-2",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[expected_review, stale_review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review(
                "own", "rep", 1, "expected_sha", 3
            )
        assert exit_code == verify_review.EXIT_DUPLICATE_REVIEW

    def test_returns_exit_duplicate_when_multiple_matching_reviews(self):
        review_a = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": "abc1234",
            "html_url": "url1",
        }
        review_b = {
            "id": 2,
            "body": "## Loop 3 Audit - Second",
            "commit_id": "abc1234",
            "html_url": "url2",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[review_a, review_b]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == verify_review.EXIT_DUPLICATE_REVIEW


class DescribeVerifyPrReviewCollectionNamingPrefix:
    """List-collection variables inside verify_pr_review must use the
    `all_` prefix per CODE_RULES §5 (consistent with `all_reviews`,
    `all_expected_headers`, `all_command` in the same function).
    """

    def test_verify_pr_review_local_variables_use_all_prefix(self):
        verify_pr_review_source_text = inspect.getsource(verify_review.verify_pr_review)
        assert "all_matching_reviews = [" in verify_pr_review_source_text
        assert "all_reviews_on_expected_commit = [" in verify_pr_review_source_text
        assert "all_stale_commits = {" in verify_pr_review_source_text
        assert " stale_commits = {" not in verify_pr_review_source_text


class DescribeCoerceOptionalStringUsesDomainParameter:
    """The `_coerce_optional_string` parameter must avoid the banned word
    `value` and use the domain term `maybe_field` (CODE_RULES §5 banned-name
    list).
    """

    def test_coerce_optional_string_parameter_named_maybe_field(self):
        coerce_signature = inspect.signature(verify_review._coerce_optional_string)
        assert "maybe_field" in coerce_signature.parameters
        assert "maybe_value" not in coerce_signature.parameters

    def test_coerce_optional_string_body_references_maybe_field(self):
        coerce_source_text = inspect.getsource(verify_review._coerce_optional_string)
        assert "isinstance(maybe_field, str)" in coerce_source_text
        assert "maybe_value" not in coerce_source_text


class DescribeMainUsesParsedArgumentsName:
    """The `main()` entry point must avoid the `args` abbreviation per
    CODE_RULES §5 (no-abbreviations) and use `parsed_arguments` to match the
    sibling `post_audit_review.py` script.
    """

    def test_main_source_uses_parsed_arguments_identifier(self):
        main_source_text = inspect.getsource(verify_review.main)
        assert "parsed_arguments = " in main_source_text
        assert "args = " not in main_source_text

    def test_main_source_does_not_reference_bare_args_attribute(self):
        main_source_text = inspect.getsource(verify_review.main)
        assert "args." not in main_source_text


class DescribeVerifyPrReviewStatusFieldImportsConstant:
    """The `status` field of the JSON success payload must be sourced from
    `STATUS_OK` in `config.review_posting_constants` rather than an inline
    literal in the function body (CODE_RULES.md magic-values rule).
    """

    def test_verify_pr_review_uses_status_ok_constant(self):
        verify_pr_review_source_text = inspect.getsource(verify_review.verify_pr_review)
        assert "STATUS_OK" in verify_pr_review_source_text
        assert '"status": "ok"' not in verify_pr_review_source_text

    def test_verify_review_module_imports_status_ok(self):
        assert hasattr(verify_review, "STATUS_OK")
        assert verify_review.STATUS_OK == "ok"

    def test_verify_pr_review_emits_status_ok_in_success_payload(self):
        sample_review = {
            "id": 99,
            "body": "## Loop 3 Audit",
            "commit_id": "abc1234",
            "html_url": "https://github.com/own/rep/pull/1#review-99",
        }
        captured_stdout: list[str] = []

        def capture_print(serialized: str) -> None:
            captured_stdout.append(serialized)

        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[sample_review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ), patch("builtins.print", side_effect=capture_print):
            verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        emitted_payload = json.loads(captured_stdout[0])
        assert emitted_payload["status"] == verify_review.STATUS_OK


class DescribePositiveIntArgparseValidation:
    """`--loop` and `--number` must reject zero and negative values at the
    argparse layer. A negative loop number silently produces a non-matching
    header and exits EXIT_NO_REVIEW, masquerading as 'no review found'
    rather than 'bad input'.
    """

    def test_rejects_zero_loop(self):
        with patch.object(
            sys,
            "argv",
            [
                "verify_review.py",
                "--owner",
                "o",
                "--repo",
                "r",
                "--number",
                "1",
                "--commit-id",
                "c",
                "--loop",
                "0",
            ],
        ):
            try:
                verify_review.main()
            except SystemExit as exit_error:
                assert exit_error.code != 0
                return
        assert False, "expected SystemExit for --loop 0"

    def test_rejects_negative_loop(self):
        with patch.object(
            sys,
            "argv",
            [
                "verify_review.py",
                "--owner",
                "o",
                "--repo",
                "r",
                "--number",
                "1",
                "--commit-id",
                "c",
                "--loop",
                "-1",
            ],
        ):
            try:
                verify_review.main()
            except SystemExit as exit_error:
                assert exit_error.code != 0
                return
        assert False, "expected SystemExit for --loop -1"

    def test_rejects_zero_number(self):
        with patch.object(
            sys,
            "argv",
            [
                "verify_review.py",
                "--owner",
                "o",
                "--repo",
                "r",
                "--number",
                "0",
                "--commit-id",
                "c",
                "--loop",
                "1",
            ],
        ):
            try:
                verify_review.main()
            except SystemExit as exit_error:
                assert exit_error.code != 0
                return
        assert False, "expected SystemExit for --number 0"

    def test_accepts_positive_loop_and_number(self):
        with patch.object(
            sys,
            "argv",
            [
                "verify_review.py",
                "--owner",
                "o",
                "--repo",
                "r",
                "--number",
                "1",
                "--commit-id",
                "c",
                "--loop",
                "1",
            ],
        ), patch.object(
            verify_review,
            "verify_pr_review",
            return_value=0,
        ):
            assert verify_review.main() == 0


class DescribeVerifyPrReviewDropsRedundantRepoFlag:
    """`verify_pr_review` must NOT pass `-R owner/repo` to gh because the
    endpoint path itself is `/repos/{owner}/{repo}/pulls/{pull_number}/reviews`
    -- the repo flag is redundant and inconsistent with the sibling code in
    `_fetch_inline_review_comments`.
    """

    def test_gh_invocation_excludes_dash_r_flag(self):
        captured_invocation: list[list[str]] = []

        def capture_run_gh(all_command, *_args, **_kwargs):
            captured_invocation.append(list(all_command))
            return type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )()

        with patch.object(verify_review, "run_gh", side_effect=capture_run_gh):
            verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert captured_invocation, "run_gh was not called"
        gh_invocation = captured_invocation[0]
        assert "-R" not in gh_invocation
        assert "own/rep" not in gh_invocation


class DescribeStaleCommitsCoercesNullCommitId:
    """`all_stale_commits` must coerce a null/non-string commit_id to
    MISSING_STRING_FIELD. When `commit_id` is present but null, dict.get
    returns None (the default only fires for absent keys), producing
    {None} in the diagnostic log rather than {""}.
    """

    def test_null_commit_id_coerced_to_missing_string_field(self):
        review_with_null_commit = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": None,
            "html_url": "url",
        }
        captured_stderr: list[str] = []

        def capture_print(*args, **kwargs):
            if kwargs.get("file") is sys.stderr:
                captured_stderr.append(" ".join(str(each_arg) for each_arg in args))

        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[review_with_null_commit]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ), patch("builtins.print", side_effect=capture_print):
            exit_code = verify_review.verify_pr_review(
                "own", "rep", 1, "expected_sha", 3
            )
        assert exit_code == 2
        joined_stderr = "\n".join(captured_stderr)
        assert "None" not in joined_stderr.split("expected")[0]


class DescribeMissingStringFieldConstantReplacesMagicEmptyString:
    """The empty-string default in `.get(key, "")` calls is a magic value in
    a production function body. The constant `MISSING_STRING_FIELD` from
    `config.review_posting_constants` is the named replacement.
    """

    def test_verify_review_imports_missing_string_field_constant(self):
        assert hasattr(verify_review, "MISSING_STRING_FIELD")
        assert verify_review.MISSING_STRING_FIELD == ""
        assert isinstance(verify_review.MISSING_STRING_FIELD, str)

    def test_verify_pr_review_uses_missing_string_field_for_html_url_default(self):
        verify_pr_review_source_text = inspect.getsource(verify_review.verify_pr_review)
        coerce_helper_source_text = inspect.getsource(
            verify_review._coerce_string_with_default
        )
        assert "MISSING_STRING_FIELD" in coerce_helper_source_text
        assert '"html_url", ""' not in verify_pr_review_source_text
        assert '"commit_id", ""' not in verify_pr_review_source_text


class DescribeSuccessPayloadCoercesNullStringFields:
    """The success-path JSON payload must apply `_coerce_string_with_default`
    to every string field read from the review object. A present-but-null
    `html_url` (or coercible-but-missing `id`) returns None from `dict.get`
    (the default only fires for absent keys), and emitting None for these
    fields breaks the orchestrator's string contract.
    """

    def test_null_html_url_coerced_to_missing_string_field_in_payload(self):
        review_with_null_url = {
            "id": 99,
            "body": "## Loop 3 Audit",
            "commit_id": "abc1234",
            "html_url": None,
        }
        captured_stdout: list[str] = []

        def capture_print(*args, **kwargs):
            if kwargs.get("file") is not sys.stderr:
                captured_stdout.append(
                    " ".join(str(each_arg) for each_arg in args)
                )

        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[review_with_null_url]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ), patch("builtins.print", side_effect=capture_print):
            exit_code = verify_review.verify_pr_review(
                "own", "rep", 1, "abc1234", 3
            )
        assert exit_code == 0
        emitted_payload = json.loads(captured_stdout[0])
        assert emitted_payload["review_url"] == verify_review.MISSING_STRING_FIELD
        assert emitted_payload["review_url"] is not None

    def test_null_review_id_coerced_to_missing_string_field_in_payload(self):
        review_with_null_id = {
            "id": None,
            "body": "## Loop 3 Audit",
            "commit_id": "abc1234",
            "html_url": "https://github.com/own/rep/pull/1#review-99",
        }
        captured_stdout: list[str] = []

        def capture_print(*args, **kwargs):
            if kwargs.get("file") is not sys.stderr:
                captured_stdout.append(
                    " ".join(str(each_arg) for each_arg in args)
                )

        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[review_with_null_id]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ), patch("builtins.print", side_effect=capture_print):
            exit_code = verify_review.verify_pr_review(
                "own", "rep", 1, "abc1234", 3
            )
        assert exit_code == 0
        emitted_payload = json.loads(captured_stdout[0])
        assert emitted_payload["review_id"] == verify_review.MISSING_STRING_FIELD
        assert emitted_payload["review_id"] is not None

    def test_success_payload_uses_coerce_helper_for_html_url_and_review_id(self):
        verify_pr_review_source_text = inspect.getsource(
            verify_review.verify_pr_review
        )
        assert (
            '_coerce_string_with_default(found_review.get("html_url"))'
            in verify_pr_review_source_text
        )
        assert (
            '_coerce_string_with_default(found_review.get("id"))'
            in verify_pr_review_source_text
        )
        assert 'found_review.get("html_url", MISSING_STRING_FIELD)' not in (
            verify_pr_review_source_text
        )
