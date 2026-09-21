"""The contrast-framing form list stays usable by both linters."""

from __future__ import annotations

from dev_env_scripts_constants.contrast_framing_constants import (
    ALL_CONTRAST_FRAMING_FORMS,
    CONTRAST_FRAMING_MESSAGE_TEMPLATE,
)


def test_every_form_carries_a_distinct_name() -> None:
    all_names = [each_form.name for each_form in ALL_CONTRAST_FRAMING_FORMS]

    assert len(set(all_names)) == len(all_names)


def test_no_form_matches_prose_that_states_what_is() -> None:
    all_clean_lines = (
        "The function runs more than 30 lines.",
        "The check names the failing line and the fix.",
        "Push the branch and read the verdict.",
        "Three attempts, then park the member.",
    )
    for each_form in ALL_CONTRAST_FRAMING_FORMS:
        for each_line in all_clean_lines:
            assert each_form.pattern.search(each_line) is None


def test_every_pattern_reports_the_words_that_carry_the_contrast() -> None:
    all_expected_matches = {
        "trailing-comma-not": (", not s", "a diff regression, not shared code"),
        "corrective-it-is-not": (
            "it is not a flake, it is",
            "it is not a flake, it is a bug",
        ),
        "substitution-rather-than": ("rather than", "park it rather than fix it"),
        "additive-not-just": ("not just", "not just for today"),
        "comparative-ranking": (
            "matters more than",
            "precision matters more than coverage",
        ),
        "substitution-as-opposed-to": (
            "as opposed to",
            "a warning as opposed to a failure",
        ),
    }
    for each_form in ALL_CONTRAST_FRAMING_FORMS:
        expected_text, example_line = all_expected_matches[each_form.name]
        assert each_form.pattern.search(example_line).group(0) == expected_text


def test_the_message_template_carries_the_three_parts() -> None:
    message = CONTRAST_FRAMING_MESSAGE_TEMPLATE.format(
        name="trailing-comma-not", text="a fix, not a workaround", guidance="State it."
    )

    assert "trailing-comma-not" in message
    assert "a fix, not a workaround" in message
    assert message.endswith("State it.")
