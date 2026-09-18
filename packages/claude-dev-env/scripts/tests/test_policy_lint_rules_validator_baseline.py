"""Validator diagnostics report only the findings a change introduces.

The code-rule adapter already compares a document against its prior text, so a
long function nobody touched stays quiet there. The validator adapter graded the
post-edit text alone, so a single-line edit to a long module reported every
pre-existing cap breach in it and failed the change on debt it did not create.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from policy_lint import adapters
from policy_lint.model import ContentOrigin, Diagnostic, Document
from policy_lint.selection import _changed_lines

FUNCTION_LENGTH_MESSAGE_FRAGMENT = "lines (max"
FILE_LENGTH_MESSAGE_FRAGMENT = "File is"
PRODUCTION_RELATIVE_PATH = "packages/claude-dev-env/scripts/sample_capped_module.py"
OVER_THRESHOLD_BODY_LINE_COUNT = 45
UNDER_THRESHOLD_BODY_LINE_COUNT = 10
OVER_FILE_CAP_FUNCTION_COUNT = 12
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _counting_function_source(function_name: str, body_line_count: int) -> str:
    all_body_lines = [
        f"    running_total = running_total + {each_index}"
        for each_index in range(body_line_count)
    ]
    return (
        "\n".join(
            [f"def {function_name}(running_total: int) -> int:"]
            + all_body_lines
            + ["    return running_total"]
        )
        + "\n"
    )


def _document(prior_text: str | None, current_text: str) -> Document:
    return Document(
        PurePosixPath(PRODUCTION_RELATIVE_PATH),
        current_text,
        prior_text,
        _changed_lines(prior_text, current_text),
        ContentOrigin.REVISION_DIFF,
    )


def _messages_carrying(document: Document, fragment: str) -> tuple[str, ...]:
    all_diagnostics: tuple[Diagnostic, ...] = adapters.validator_diagnostics(
        document, REPOSITORY_ROOT
    )
    return tuple(
        each_diagnostic.message
        for each_diagnostic in all_diagnostics
        if fragment in each_diagnostic.message
    )


def _function_length_messages(
    prior_text: str | None, current_text: str
) -> tuple[str, ...]:
    return _messages_carrying(
        _document(prior_text, current_text), FUNCTION_LENGTH_MESSAGE_FRAGMENT
    )


def _over_file_cap_source(extra_line: str = "") -> str:
    all_functions = [
        _counting_function_source(
            f"each_step_{each_index}", OVER_THRESHOLD_BODY_LINE_COUNT
        )
        for each_index in range(OVER_FILE_CAP_FUNCTION_COUNT)
    ]
    return extra_line + "\n".join(all_functions)


def test_should_leave_an_untouched_long_function_alone() -> None:
    prior_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    current_text = f"import os\nimport sys\n{prior_text}"
    assert _function_length_messages(prior_text, current_text) == ()


def test_should_report_an_over_long_function_the_change_adds() -> None:
    prior_text = _counting_function_source("existing", UNDER_THRESHOLD_BODY_LINE_COUNT)
    added_text = _counting_function_source("added", OVER_THRESHOLD_BODY_LINE_COUNT)
    assert _function_length_messages(prior_text, f"{prior_text}\n{added_text}") != ()


def test_should_report_a_function_the_change_grew_past_the_cap() -> None:
    prior_text = _counting_function_source("main", UNDER_THRESHOLD_BODY_LINE_COUNT)
    current_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    assert _function_length_messages(prior_text, current_text) != ()


def test_should_report_every_cap_breach_in_a_wholly_new_document() -> None:
    current_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    assert _function_length_messages(None, current_text) != ()


def test_should_report_a_cap_breach_when_the_selection_names_no_prior_text() -> None:
    current_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    document = Document(
        PurePosixPath(PRODUCTION_RELATIVE_PATH),
        current_text,
        None,
        None,
        ContentOrigin.WORKTREE,
    )
    assert _messages_carrying(document, FUNCTION_LENGTH_MESSAGE_FRAGMENT) != ()


def test_should_leave_an_over_cap_file_alone_when_the_change_only_shrinks_it() -> None:
    prior_text = _over_file_cap_source("REMOVED_SETTING = 1\n")
    current_text = _over_file_cap_source()
    document = _document(prior_text, current_text)
    assert _messages_carrying(document, FILE_LENGTH_MESSAGE_FRAGMENT) == ()


def test_should_report_a_file_the_change_pushed_over_the_cap() -> None:
    prior_text = _counting_function_source("main", UNDER_THRESHOLD_BODY_LINE_COUNT)
    current_text = _over_file_cap_source()
    document = _document(prior_text, current_text)
    assert _messages_carrying(document, FILE_LENGTH_MESSAGE_FRAGMENT) != ()
