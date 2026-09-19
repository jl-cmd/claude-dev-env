import pytest

from shop.cart import bulk_discount_percent, line_total


@pytest.mark.parametrize(
    ("quantity", "percent"), [(1, 0), (9, 0), (10, 5), (49, 5), (50, 12), (500, 12)]
)
def test_tiers(quantity, percent):
    assert bulk_discount_percent(quantity) == percent


def test_line_total_applies_tier():
    assert line_total(100, 10) == 950
    assert line_total(100, 9) == 900
    assert line_total(99, 50) == 4356


def test_line_total_rounds_half_up():
    assert line_total(33, 10) == 314


@pytest.mark.parametrize("quantity", [0, -3])
def test_rejects_quantity_below_one(quantity):
    with pytest.raises(ValueError):
        bulk_discount_percent(quantity)
    with pytest.raises(ValueError):
        line_total(100, quantity)
