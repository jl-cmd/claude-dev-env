from catalog.paging import page_count, paginate


def test_full_pages():
    assert paginate(["a", "b", "c", "d"], 2, 2) == ["c", "d"]


def test_page_count_even():
    assert page_count(4, 2) == 2
