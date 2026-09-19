import pytest

from catalog.paging import page_count, paginate


def test_partial_last_page_is_returned():
    assert paginate(["a", "b", "c", "d", "e"], 3, 2) == ["e"]


def test_page_count_counts_partial_page():
    assert page_count(5, 2) == 3
    assert page_count(4, 2) == 2
    assert page_count(0, 2) == 0


def test_page_past_end_is_empty():
    assert paginate(["a", "b", "c"], 3, 2) == []


def test_size_must_be_positive():
    with pytest.raises(ValueError):
        page_count(3, 0)
