import pytest

from shop.pricing import apply_discount


def test_no_discount_keeps_price():
    assert apply_discount(1000, 0) == 1000


def test_even_discount():
    assert apply_discount(1000, 25) == 750


def test_rejects_percent_above_hundred():
    with pytest.raises(ValueError):
        apply_discount(1000, 101)
