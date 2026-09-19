import pytest

from shop.pricing import apply_discount


@pytest.mark.parametrize(
    ("price_cents", "percent", "expected"),
    [(1050, 15, 893), (333, 50, 167), (999, 15, 849), (1000, 25, 750), (1, 50, 1), (1010, 15, 859)],
)
def test_rounds_half_up(price_cents, percent, expected):
    assert apply_discount(price_cents, percent) == expected


def test_still_rejects_bad_percent():
    with pytest.raises(ValueError):
        apply_discount(100, -1)
