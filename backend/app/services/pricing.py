"""Authoritative money calculation (backend only; the frontend never prices anything).

    subtotal = price_per_kg * weight_grams / 1000, rounded to 2 decimals (ROUND_HALF_UP)
    total    = sum of the ROUNDED line subtotals

Summing rounded subtotals (not rounding the raw sum) guarantees that the lines shown
on a cart or receipt always add up exactly to the total. Weights are integer grams and
prices are Decimal, so no floating point is involved. ROUND_HALF_UP is used instead of
Python's default banker's rounding so 14.985 becomes 14.99, as shoppers expect.
"""
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")
_GRAMS_PER_KG = Decimal(1000)


def money(value: Decimal) -> Decimal:
    """Round to 2 decimal places, half up."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def calculate_subtotal(price_per_kg: Decimal, weight_grams: int) -> Decimal:
    if weight_grams < 0:
        raise ValueError("weight_grams must not be negative")
    return money(Decimal(price_per_kg) * Decimal(weight_grams) / _GRAMS_PER_KG)


def calculate_total(subtotals: Iterable[Decimal]) -> Decimal:
    return money(sum(subtotals, Decimal("0")))
