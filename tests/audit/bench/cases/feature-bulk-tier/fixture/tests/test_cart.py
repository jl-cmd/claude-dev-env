from shop.cart import line_total


def test_single_item():
    assert line_total(250, 1) == 250
