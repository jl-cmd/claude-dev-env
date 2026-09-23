"""Behavior tests for the hashed private-term matcher."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from dev_env_scripts_constants.private_term_constants import PrivateTermDigest
from private_terms import names_private_term, private_term_line_numbers

_FIXTURE_TERM = "acmewidget"
_ALL_FIXTURE_DIGESTS = frozenset(
    {
        PrivateTermDigest(
            length=len(_FIXTURE_TERM),
            sha256=hashlib.sha256(_FIXTURE_TERM.encode("utf-8")).hexdigest(),
        )
    }
)


def test_should_report_the_line_of_a_spaced_spelling() -> None:
    text = "first line\nBuilt for Acme Widgets, Inc. last year\nthird line\n"
    assert private_term_line_numbers(text, _ALL_FIXTURE_DIGESTS) == (2,)


def test_should_report_a_hyphenated_owner_in_a_link() -> None:
    text = "See https://github.com/Acme-Widgets-Inc/tools/pull/12 for detail."
    assert private_term_line_numbers(text, _ALL_FIXTURE_DIGESTS) == (1,)


def test_should_report_an_email_domain() -> None:
    text = "Co-authored-by: Pat <pat@ACMEWIDGETS.EXAMPLE.COM>"
    assert private_term_line_numbers(text, _ALL_FIXTURE_DIGESTS) == (1,)


def test_should_report_a_term_split_across_a_line_break_at_its_first_line() -> None:
    text = "one\nsold by Acme\nWidgets today\n"
    assert private_term_line_numbers(text, _ALL_FIXTURE_DIGESTS) == (2,)


def test_should_report_each_line_once() -> None:
    text = "acme widget and acme-widget\nclean\nAcmeWidget\n"
    assert private_term_line_numbers(text, _ALL_FIXTURE_DIGESTS) == (1, 3)


def test_should_report_nothing_for_clean_text() -> None:
    text = "An acme of widgets.\nWidget acme.\n"
    assert private_term_line_numbers(text, _ALL_FIXTURE_DIGESTS) == ()
    assert not names_private_term(text, _ALL_FIXTURE_DIGESTS)


def test_should_answer_whether_text_names_a_term() -> None:
    assert names_private_term("Acme-Widgets-Inc", _ALL_FIXTURE_DIGESTS)
