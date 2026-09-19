def line_total(unit_cents: int, quantity: int) -> int:
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    return unit_cents * quantity
