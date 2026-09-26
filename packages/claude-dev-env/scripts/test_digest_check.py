"""Tests for the digest page check."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

import digest_check
from dev_env_scripts_constants.digest_check_constants import (
    CARD_WORD_BUDGET,
    LEAD_WORD_BUDGET,
)

PICTURE = '<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'


def _card(card_id: str, words: str, picture: str = PICTURE) -> str:
    return f'<section data-digest-card="{card_id}">{picture}<p>{words}</p></section>'


def _page(*all_parts: str, lead: str = "Merged today") -> str:
    body = "".join(all_parts)
    return (
        "<!doctype html><html><head><title>Digest</title>"
        "<style>p{margin:0}</style></head>"
        f"<body><h1>{lead}</h1>{body}"
        "<script>const words = 'one two three four five';</script></body></html>"
    )


def _findings(page_html: str, all_expected_ids: list[str]) -> list[str]:
    page = digest_check.read_digest_page(page_html)
    return digest_check.digest_findings(page, all_expected_ids)


def test_page_covering_every_card_briefly_with_pictures_passes() -> None:
    page_html = _page(
        _card("4701", "Search now keeps your filters."),
        _card("4702", "Exports finish twice as fast."),
    )
    assert _findings(page_html, ["4701", "4702"]) == []


def test_page_leaving_out_an_expected_card_reports_it() -> None:
    page_html = _page(_card("4701", "Search now keeps your filters."))
    assert _findings(page_html, ["4701", "4715"]) == [
        "missing card 4715: the page leaves it out"
    ]


def test_card_over_the_word_budget_reports_its_count() -> None:
    long_words = " ".join(["word"] * (CARD_WORD_BUDGET + 1))
    page_html = _page(_card("4701", long_words))
    assert _findings(page_html, ["4701"]) == [
        f"card 4701 carries {CARD_WORD_BUDGET + 1} words; "
        f"the budget is {CARD_WORD_BUDGET}"
    ]


def test_card_at_the_word_budget_passes() -> None:
    page_html = _page(_card("4701", " ".join(["word"] * CARD_WORD_BUDGET)))
    assert _findings(page_html, ["4701"]) == []


def test_card_without_a_picture_reports_it() -> None:
    page_html = _page(_card("4701", "Search now keeps your filters.", picture=""))
    assert _findings(page_html, ["4701"]) == ["card 4701 has no picture"]


def test_self_closing_image_counts_as_a_picture() -> None:
    page_html = _page(
        _card("4701", "Search now keeps your filters.", picture='<img src="a.png"/>')
    )
    assert _findings(page_html, ["4701"]) == []


def test_lead_text_over_its_budget_reports_the_count() -> None:
    long_lead = " ".join(["word"] * (LEAD_WORD_BUDGET + 1))
    page_html = _page(_card("4701", "Search now keeps your filters."), lead=long_lead)
    assert _findings(page_html, ["4701"]) == [
        f"text outside the cards carries {LEAD_WORD_BUDGET + 1} words; "
        f"the budget is {LEAD_WORD_BUDGET}"
    ]


def test_head_script_and_style_text_stay_out_of_the_count() -> None:
    page = digest_check.read_digest_page(_page(lead="Merged today"))
    assert page.lead_word_count == 2


def test_picture_label_text_counts_toward_its_card() -> None:
    labelled_picture = "<svg><text>before after</text></svg>"
    page = digest_check.read_digest_page(
        _page(_card("4701", "one two", picture=labelled_picture))
    )
    assert [each_card.word_count for each_card in page.all_cards] == [4]


def test_card_marked_twice_reports_the_duplicate() -> None:
    page_html = _page(
        _card("4701", "Search now keeps your filters."),
        _card("4701", "Search now keeps your filters."),
    )
    assert _findings(page_html, ["4701"]) == ["card 4701 appears 2 times"]


def test_main_exits_one_and_prints_findings_for_a_missing_card(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    page_path = tmp_path / "digest.html"
    page_path.write_text(_page(_card("4701", "Search keeps filters.")), encoding="utf-8")
    exit_code = digest_check.main([str(page_path), "--expect", "4701", "4702"])
    assert exit_code == 1
    assert capsys.readouterr().out == "missing card 4702: the page leaves it out\n"


def test_main_exits_zero_and_names_the_count_for_a_clean_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    page_path = tmp_path / "digest.html"
    page_path.write_text(_page(_card("4701", "Search keeps filters.")), encoding="utf-8")
    exit_code = digest_check.main([str(page_path), "--expect", "4701"])
    assert exit_code == 0
    assert capsys.readouterr().out == "CLEAN: 1 cards, every one present\n"


def test_markup_inside_a_script_leaves_the_cards_intact() -> None:
    page_html = _page(
        "<script>if (a<b) { x = '<div data-digest-card=\"9\">'; }</script>",
        _card("4701", "Search keeps filters."),
    )
    assert _findings(page_html, ["4701"]) == []


def test_single_quoted_card_marker_and_entities_parse() -> None:
    page = digest_check.read_digest_page(
        f"<div data-digest-card='4701'>{PICTURE}<p>Fish &amp; chips</p></div>"
    )
    assert [(each_card.card_id, each_card.word_count) for each_card in page.all_cards] == [
        ("4701", 2)
    ]
