"""Tests for the shared abbreviation_checks allow-list constant."""

from .abbreviation_checks_constants import ALL_ALLOWED_SINGLE_LETTERS


def test_allowed_single_letters_covers_loop_counters_and_underscore() -> None:
    assert ALL_ALLOWED_SINGLE_LETTERS == frozenset({"i", "j", "k", "_"})


def test_allowed_single_letters_is_immutable() -> None:
    assert isinstance(ALL_ALLOWED_SINGLE_LETTERS, frozenset)
