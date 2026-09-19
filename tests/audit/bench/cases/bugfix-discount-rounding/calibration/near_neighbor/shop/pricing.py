from decimal import ROUND_HALF_UP, Decimal


def apply_discount(price_cents: int, percent: int) -> int:
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    discounted = Decimal(price_cents) * Decimal(100 - percent) / Decimal(100)
    return int(discounted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
