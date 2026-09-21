"""Behavior of the contrast-framing detector and its rule document."""

from __future__ import annotations

from pathlib import Path

import pytest
from contrast_framing import (
    describe_contrast_framing,
    find_contrast_framing,
    form_named,
)
from dev_env_scripts_constants.contrast_framing_constants import (
    ALL_CONTRAST_FRAMING_FORMS,
    CONTRAST_FRAMING_RULE_DOCUMENT,
)

PACKAGE_ROOT: Path = Path(__file__).resolve().parents[2]


def _form_names(document_text: str) -> list[str]:
    return [each_hit[2] for each_hit in find_contrast_framing(document_text)]


def test_trailing_comma_not_reports() -> None:
    assert _form_names("A diff regression, not shared infrastructure.\n") == [
        "trailing-comma-not"
    ]


def test_corrective_it_is_not_reports() -> None:
    assert "corrective-it-is-not" in _form_names("It's not a flake, it's a bug.\n")


def test_comparative_ranking_reports() -> None:
    document_text = "Being precise about them matters more than trying to cover them.\n"
    assert "comparative-ranking" in _form_names(document_text)


def test_substitution_and_additive_forms_report() -> None:
    document_text = "Park it rather than fix it, and not just for today.\n"
    assert set(_form_names(document_text)) >= {
        "substitution-rather-than",
        "additive-not-just",
    }


def test_plain_quantity_comparison_stays_quiet() -> None:
    assert _form_names("The function runs more than 30 lines.\n") == []


def test_statement_of_what_is_stays_quiet() -> None:
    document_text = (
        "The check reports the failing line and names the fix.\n"
        "Push the branch and read the verdict.\n"
    )
    assert _form_names(document_text) == []


def test_code_span_and_fence_contents_stay_quiet() -> None:
    document_text = (
        "Call `parse(value, not_found)` for the missing case.\n"
        "```\n"
        "returns a value, not a default\n"
        "```\n"
    )
    assert _form_names(document_text) == []


def test_reported_line_and_column_locate_the_match() -> None:
    document_text = "First line.\nOne answer, not two.\n"
    assert find_contrast_framing(document_text) == [(2, 11, "trailing-comma-not")]


def test_message_names_the_form_the_text_and_the_fix() -> None:
    document_text = "One answer, not two.\n"
    line_number, _column, form_name = find_contrast_framing(document_text)[0]
    source_line = document_text.splitlines()[line_number - 1]
    message = describe_contrast_framing(source_line, form_name)
    assert "trailing-comma-not" in message
    assert "state what is true" in message.lower()


def test_form_named_rejects_an_unknown_name() -> None:
    with pytest.raises(KeyError):
        form_named("no-such-form")


def test_every_form_carries_a_row_in_the_rule_document() -> None:
    rule_text = (PACKAGE_ROOT / CONTRAST_FRAMING_RULE_DOCUMENT).read_text(
        encoding="utf-8"
    )
    for each_form in ALL_CONTRAST_FRAMING_FORMS:
        assert f"`{each_form.name}`" in rule_text


def test_a_list_of_not_items_stays_quiet() -> None:
    document_text = "Not in chat, not in a commit message, not in a body.\n"
    assert _form_names(document_text) == []


def test_a_quoted_line_stays_quiet() -> None:
    assert _form_names("> a bug, not a flake\n") == []
