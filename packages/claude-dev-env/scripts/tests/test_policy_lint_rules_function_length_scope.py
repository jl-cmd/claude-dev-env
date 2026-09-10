"""Function-length diagnostics report only functions the change is responsible for.

The code-rule adapter runs the enforcer with ``defer_scope_to_caller`` set, so
the enforcer hands back every over-long function in the document and the caller
owns the scope decision. The engine's own changed-line filter keys on a
diagnostic's start line, and a function-length message carries no ``Line N:``
prefix, so before this scope pass a pre-existing long function blocked any
change that touched its file.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from policy_lint import adapters
from policy_lint.model import ContentOrigin, Diagnostic, Document
from policy_lint.selection import _changed_lines

FUNCTION_LENGTH_MESSAGE_FRAGMENT = "exceeds blocking threshold"
PRODUCTION_RELATIVE_PATH = "packages/claude-dev-env/scripts/sample_long_module.py"
OVER_THRESHOLD_BODY_LINE_COUNT = 70
UNDER_THRESHOLD_BODY_LINE_COUNT = 40
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _counting_function_source(function_name: str, body_line_count: int) -> str:
    all_body_lines = [
        f"    running_total = running_total + {each_index}"
        for each_index in range(body_line_count)
    ]
    signature_lines = [f"def {function_name}(running_total: int) -> int:"]
    return (
        "\n".join(signature_lines + all_body_lines + ["    return running_total"])
        + "\n"
    )


def _messages_for_document(document: Document) -> tuple[str, ...]:
    all_diagnostics: tuple[Diagnostic, ...] = adapters.code_rule_diagnostics(
        document, REPOSITORY_ROOT
    )
    return tuple(
        each_diagnostic.message
        for each_diagnostic in all_diagnostics
        if FUNCTION_LENGTH_MESSAGE_FRAGMENT in each_diagnostic.message
    )


def _function_length_messages(
    prior_text: str | None, current_text: str
) -> tuple[str, ...]:
    return _messages_for_document(
        Document(
            PurePosixPath(PRODUCTION_RELATIVE_PATH),
            current_text,
            prior_text,
            _changed_lines(prior_text, current_text),
            ContentOrigin.REVISION_DIFF,
        )
    )


def test_should_leave_an_untouched_long_function_alone() -> None:
    prior_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    current_text = f"import os\nimport sys\n{prior_text}"
    assert _function_length_messages(prior_text, current_text) == ()


def test_should_report_a_function_the_change_grew_past_the_threshold() -> None:
    prior_text = _counting_function_source("main", UNDER_THRESHOLD_BODY_LINE_COUNT)
    current_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    assert _function_length_messages(prior_text, current_text) != ()


def test_should_report_an_over_long_function_the_change_adds() -> None:
    prior_text = _counting_function_source("existing", UNDER_THRESHOLD_BODY_LINE_COUNT)
    added_text = _counting_function_source("added", OVER_THRESHOLD_BODY_LINE_COUNT)
    assert _function_length_messages(prior_text, f"{prior_text}\n{added_text}") != ()


def test_should_report_every_over_long_function_in_a_wholly_new_document() -> None:
    current_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    assert _function_length_messages(None, current_text) != ()


def test_should_leave_a_long_function_alone_when_the_change_only_deletes() -> None:
    current_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    prior_text = f"REMOVED_CONSTANT = 1\n{current_text}"
    assert _function_length_messages(prior_text, current_text) == ()


def test_should_report_a_long_function_when_the_selection_names_no_changed_lines() -> None:
    current_text = _counting_function_source("main", OVER_THRESHOLD_BODY_LINE_COUNT)
    document = Document(
        PurePosixPath(PRODUCTION_RELATIVE_PATH),
        current_text,
        None,
        None,
        ContentOrigin.WORKTREE,
    )
    assert _messages_for_document(document) != ()
