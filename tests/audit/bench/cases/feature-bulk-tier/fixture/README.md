# shop cart

Planned: bulk pricing.

| Quantity | Discount percent |
|---|---|
| 1 to 9 | 0 |
| 10 to 49 | 5 |
| 50 and up | 12 |

`shop.cart.bulk_discount_percent(quantity)` returns the percent.
`shop.cart.line_total(unit_cents, quantity)` returns the discounted line total
in whole cents, fractional cents rounded half up. A quantity below 1 raises
`ValueError` from both functions.
