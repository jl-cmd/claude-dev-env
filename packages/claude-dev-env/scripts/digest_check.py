#!/usr/bin/env python3
"""Check that a digest page lets its reader read less and still know all.

A digest page summarizes a set of changes, such as the pull requests merged in
a day. Each change gets one card, marked with ``data-digest-card="<id>"``,
that holds its picture and its one-line change.

::

    python digest_check.py summary.html --expect 4701 4702 4715
    ok:   CLEAN: 3 cards, every one present
    flag: missing card 4715: the page leaves it out
    flag: card 4701 carries 31 words; the budget is 25
    flag: card 4702 has no picture

The check also reports lead text over its own budget and a card marked twice.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from dev_env_scripts_constants.digest_check_constants import (
    ALL_HIDDEN_TEXT_TAGS,
    ALL_PICTURE_TAGS,
    ALL_RAW_TEXT_TAGS,
    ALL_VOID_TAGS,
    CARD_ATTRIBUTE_PATTERN,
    CARD_OVER_BUDGET_FINDING,
    CARD_WITHOUT_PICTURE_FINDING,
    CARD_WORD_BUDGET,
    CLEAN_VERDICT,
    DUPLICATE_CARD_FINDING,
    EXIT_CLEAN,
    EXIT_FINDINGS,
    LEAD_OVER_BUDGET_FINDING,
    LEAD_WORD_BUDGET,
    MARKUP_PATTERN,
    MISSING_CARD_FINDING,
    UTF8_ENCODING,
    WORD_PATTERN,
)


@dataclass
class DigestCard:
    """One marked card on a digest page."""

    card_id: str
    word_count: int = 0
    has_picture: bool = False


@dataclass
class DigestPage:
    """Every marked card on a page, and the words outside them."""

    all_cards: list[DigestCard] = field(default_factory=list)
    lead_word_count: int = 0


@dataclass
class _OpenElement:
    tag_name: str
    card: DigestCard | None
    is_hidden: bool


def _innermost_card(all_open: list[_OpenElement]) -> DigestCard | None:
    for each_open in reversed(all_open):
        if each_open.card is not None:
            return each_open.card
    return None


def _count_words(page: DigestPage, all_open: list[_OpenElement], text: str) -> None:
    if any(each_open.is_hidden for each_open in all_open):
        return
    word_count = len(WORD_PATTERN.findall(html.unescape(text)))
    enclosing_card = _innermost_card(all_open)
    if enclosing_card is None:
        page.lead_word_count += word_count
    else:
        enclosing_card.word_count += word_count


def _close_element(all_open: list[_OpenElement], tag_name: str) -> None:
    for each_index in range(len(all_open) - 1, -1, -1):
        if all_open[each_index].tag_name == tag_name:
            del all_open[each_index:]
            return


def _open_element(
    page: DigestPage, all_open: list[_OpenElement], tag_match: re.Match[str]
) -> None:
    tag_name = tag_match.group("tag_name").lower()
    if tag_name in ALL_PICTURE_TAGS:
        enclosing_card = _innermost_card(all_open)
        if enclosing_card is not None:
            enclosing_card.has_picture = True
    if tag_name in ALL_VOID_TAGS or tag_match.group("self_closing"):
        return
    new_card = None
    card_match = CARD_ATTRIBUTE_PATTERN.search(tag_match.group("attributes"))
    if card_match is not None:
        card_id = card_match.group("double") or card_match.group("single") or ""
        new_card = DigestCard(card_id=html.unescape(card_id).strip())
        page.all_cards.append(new_card)
    all_open.append(_OpenElement(tag_name, new_card, tag_name in ALL_HIDDEN_TEXT_TAGS))


def read_digest_page(page_html: str) -> DigestPage:
    """Return the marked cards and lead word count of one page.

    Args:
        page_html: Full HTML source of the page.

    Returns:
        The parsed page, with words counted toward their innermost card.
    """
    page = DigestPage()
    all_open: list[_OpenElement] = []
    position = 0
    while position < len(page_html):
        tag_match = MARKUP_PATTERN.search(page_html, position)
        text_end = len(page_html) if tag_match is None else tag_match.start()
        _count_words(page, all_open, page_html[position:text_end])
        if tag_match is None:
            break
        position = tag_match.end()
        if tag_match.group("tag_name") is None:
            continue
        tag_name = tag_match.group("tag_name").lower()
        if tag_match.group("closing"):
            _close_element(all_open, tag_name)
            continue
        _open_element(page, all_open, tag_match)
        if tag_name in ALL_RAW_TEXT_TAGS and not tag_match.group("self_closing"):
            raw_end = page_html.lower().find(f"</{tag_name}", position)
            position = len(page_html) if raw_end == -1 else raw_end
    return page


def _coverage_findings(page: DigestPage, all_expected_ids: list[str]) -> list[str]:
    card_counts = Counter(each_card.card_id for each_card in page.all_cards)
    all_findings = [
        MISSING_CARD_FINDING.format(card_id=each_expected_id)
        for each_expected_id in all_expected_ids
        if card_counts[each_expected_id] == 0
    ]
    all_findings.extend(
        DUPLICATE_CARD_FINDING.format(card_id=each_card_id, count=each_count)
        for each_card_id, each_count in card_counts.items()
        if each_count > 1
    )
    return all_findings


def _budget_findings(page: DigestPage) -> list[str]:
    all_findings: list[str] = []
    for each_card in page.all_cards:
        if each_card.word_count > CARD_WORD_BUDGET:
            all_findings.append(
                CARD_OVER_BUDGET_FINDING.format(
                    card_id=each_card.card_id,
                    word_count=each_card.word_count,
                    budget=CARD_WORD_BUDGET,
                )
            )
        if not each_card.has_picture:
            all_findings.append(
                CARD_WITHOUT_PICTURE_FINDING.format(card_id=each_card.card_id)
            )
    if page.lead_word_count > LEAD_WORD_BUDGET:
        all_findings.append(
            LEAD_OVER_BUDGET_FINDING.format(
                word_count=page.lead_word_count, budget=LEAD_WORD_BUDGET
            )
        )
    return all_findings


def digest_findings(page: DigestPage, all_expected_ids: list[str]) -> list[str]:
    """Return every way the page makes its reader read more or know less.

    Args:
        page: The parsed page.
        all_expected_ids: Every source id the page must cover with a card.

    Returns:
        Coverage findings first, then budget findings; empty when the page passes.
    """
    return _coverage_findings(page, all_expected_ids) + _budget_findings(page)


def main(all_arguments: list[str]) -> int:
    """Check one page against its source ids and print the verdict.

    Args:
        all_arguments: Command-line arguments after the program name.

    Returns:
        Zero when the page passes, one when any finding reports.
    """
    argument_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argument_parser.add_argument("page", type=Path)
    argument_parser.add_argument("--expect", nargs="+", required=True)
    parsed = argument_parser.parse_args(all_arguments)
    page = read_digest_page(parsed.page.read_text(encoding=UTF8_ENCODING))
    all_findings = digest_findings(page, parsed.expect)
    for each_finding in all_findings:
        print(each_finding)
    if all_findings:
        return EXIT_FINDINGS
    print(CLEAN_VERDICT.format(card_count=len(parsed.expect)))
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
