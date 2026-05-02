"""Tests for shared gh_util.py promoted from babysit-pr/skills/babysit-prs/scripts/."""

import importlib.util
import inspect
import subprocess
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


def _load_gh_util_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "gh_util.py"
    spec = importlib.util.spec_from_file_location("gh_util", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gh_util"] = module
    spec.loader.exec_module(module)
    return module


gh_util = _load_gh_util_module()


class ParseOwnerRepositoryTests(unittest.TestCase):
    def test_accepts_owner_repo(self) -> None:
        self.assertEqual(
            gh_util.parse_owner_repo("JonEcho/babysit-pr"),
            ("JonEcho", "babysit-pr"),
        )

    def test_rejects_missing_slash(self) -> None:
        with self.assertRaises(ValueError):
            gh_util.parse_owner_repo("babysit-pr")

    def test_rejects_empty_owner(self) -> None:
        with self.assertRaises(ValueError):
            gh_util.parse_owner_repo("/babysit-pr")

    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            gh_util.parse_owner_repo("JonEcho/")

    def test_rejects_extra_slash_segment(self) -> None:
        with self.assertRaises(ValueError):
            gh_util.parse_owner_repo("JonEcho/babysit-pr/extra")


class RunGhTests(unittest.TestCase):
    def test_returns_on_first_success(self) -> None:
        success = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with patch.object(gh_util.subprocess, "run", return_value=success) as run_mock:
            with patch.object(gh_util.time, "sleep") as sleep_mock:
                result = gh_util.run_gh(("gh", "pr", "list"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(run_mock.call_count, 1)
        sleep_mock.assert_not_called()

    def test_retries_transient_failure_then_succeeds(self) -> None:
        failure = subprocess.CompletedProcess(
            args=("gh",),
            returncode=1,
            stdout="",
            stderr="connection reset by peer",
        )
        success = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with patch.object(
            gh_util.subprocess, "run", side_effect=[failure, success]
        ) as run_mock:
            with patch.object(gh_util.time, "sleep") as sleep_mock:
                result = gh_util.run_gh(("gh", "api", "ping"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(sleep_mock.call_count, 1)

    def test_does_not_retry_authentication_failure(self) -> None:
        failure = subprocess.CompletedProcess(
            args=("gh",),
            returncode=1,
            stdout="",
            stderr="HTTP 401: Bad credentials",
        )
        with patch.object(gh_util.subprocess, "run", return_value=failure) as run_mock:
            with patch.object(gh_util.time, "sleep") as sleep_mock:
                result = gh_util.run_gh(("gh", "pr", "view", "1"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(run_mock.call_count, 1)
        sleep_mock.assert_not_called()


class FetchInlineReviewCommentsTests(unittest.TestCase):
    def test_returns_parsed_list_on_success(self) -> None:
        payload = [{"id": 1, "path": "foo.py", "line": 10, "body": "Fix this please"}]
        success = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout='[{"id": 1, "path": "foo.py", "line": 10, "body": "Fix this please"}]',
            stderr="",
        )
        with patch.object(gh_util.subprocess, "run", return_value=success):
            result = gh_util.fetch_inline_review_comments("JonEcho", "babysit-pr", 17)
        self.assertEqual(result, payload)

    def test_returns_none_on_gh_failure(self) -> None:
        failure = subprocess.CompletedProcess(
            args=("gh",),
            returncode=1,
            stdout="",
            stderr="Not Found",
        )
        with patch.object(gh_util.subprocess, "run", return_value=failure):
            result = gh_util.fetch_inline_review_comments("JonEcho", "babysit-pr", 17)
        self.assertIsNone(result)

    def test_returns_none_on_invalid_json_with_success_returncode(self) -> None:
        success_with_invalid_json = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout="not valid json",
            stderr="",
        )
        with patch.object(
            gh_util.subprocess, "run", return_value=success_with_invalid_json
        ):
            result = gh_util.fetch_inline_review_comments("JonEcho", "babysit-pr", 17)
        self.assertIsNone(result)

    def test_returns_none_when_response_is_not_a_list(self) -> None:
        success_with_object = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout='{"message": "unexpected object"}',
            stderr="",
        )
        with patch.object(gh_util.subprocess, "run", return_value=success_with_object):
            result = gh_util.fetch_inline_review_comments("JonEcho", "babysit-pr", 17)
        self.assertIsNone(result)

    def test_returns_none_when_inner_items_are_not_dicts(self) -> None:
        success_with_non_dict_items = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout="[1, 2, 3]",
            stderr="",
        )
        with patch.object(
            gh_util.subprocess, "run", return_value=success_with_non_dict_items
        ):
            result = gh_util.fetch_inline_review_comments("JonEcho", "babysit-pr", 17)
        self.assertIsNone(result)

    def test_returns_none_when_inner_items_mix_dict_and_string(self) -> None:
        success_with_mixed_items = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout='[{"id": 1, "path": "a.py"}, "stray string"]',
            stderr="",
        )
        with patch.object(
            gh_util.subprocess, "run", return_value=success_with_mixed_items
        ):
            result = gh_util.fetch_inline_review_comments("JonEcho", "babysit-pr", 17)
        self.assertIsNone(result)


class RunGhUnreachableAssertionRemovedTests(unittest.TestCase):
    def test_run_gh_function_body_does_not_contain_unreachable_assertion(self) -> None:
        run_gh_source_text = inspect.getsource(gh_util.run_gh)
        assert "AssertionError" not in run_gh_source_text


class RunGhUnreachableTrailingReturnRemovedTests(unittest.TestCase):
    """Regression: every for-loop branch in run_gh returns a GhResult, so the
    trailing `return GhResult(...)` block after the loop is unreachable. The
    body must terminate with the for-loop's own returns, not a fallback block
    referencing 'exhausted all attempts'.
    """

    def test_run_gh_function_body_does_not_contain_unreachable_trailing_return(
        self,
    ) -> None:
        run_gh_source_text = inspect.getsource(gh_util.run_gh)
        assert "exhausted all attempts" not in run_gh_source_text


class EnsureTextParameterNameTests(unittest.TestCase):
    """The `_ensure_text` parameter must not use the banned name `value`.

    CODE_RULES.md §5 bans generic names like `value`. The parameter must
    describe what it carries -- a subprocess stdout/stderr field that may be
    str, bytes, or None.
    """

    def test_ensure_text_parameter_is_not_named_value(self) -> None:
        ensure_text_signature = inspect.signature(gh_util._ensure_text)
        all_parameter_names = list(ensure_text_signature.parameters)
        assert "value" not in all_parameter_names


class FetchInlineReviewCommentsPaginationTests(unittest.TestCase):
    """Regression: gh --paginate emits one JSON document per page concatenated.

    Per the project's gh-paginate rule, --paginate for a list endpoint emits
    one JSON array per page (e.g. `[...]\\n[...]\\n[...]`), and json.loads
    fails on the second `[`. fetch_inline_review_comments must merge those
    documents and return the flattened list rather than returning None.
    """

    def test_returns_flattened_list_for_concatenated_pages(self) -> None:
        page_one_body = '[{"id": 1, "path": "a.py"}, {"id": 2, "path": "b.py"}]'
        page_two_body = '[{"id": 3, "path": "c.py"}]'
        concatenated_pages = f"{page_one_body}\n{page_two_body}\n"
        success = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout=concatenated_pages,
            stderr="",
        )
        with patch.object(gh_util.subprocess, "run", return_value=success):
            fetched_comments = gh_util.fetch_inline_review_comments(
                "JonEcho", "babysit-pr", 17
            )
        assert fetched_comments == [
            {"id": 1, "path": "a.py"},
            {"id": 2, "path": "b.py"},
            {"id": 3, "path": "c.py"},
        ]

    def test_returns_none_when_concatenated_page_is_not_a_list(self) -> None:
        concatenated_with_object = '[{"id": 1}]\n{"message": "oops"}\n'
        success = subprocess.CompletedProcess(
            args=("gh",),
            returncode=0,
            stdout=concatenated_with_object,
            stderr="",
        )
        with patch.object(gh_util.subprocess, "run", return_value=success):
            fetched_comments = gh_util.fetch_inline_review_comments(
                "JonEcho", "babysit-pr", 17
            )
        assert fetched_comments is None


if __name__ == "__main__":
    unittest.main()
