from decimal import Decimal

import pytest

from app.services.pricing import calculate_subtotal, calculate_total, money

D = Decimal


def test_subtotal_formula():
    assert calculate_subtotal(D("60.00"), 320) == D("19.20")
    assert calculate_subtotal(D("90.00"), 500) == D("45.00")
    assert calculate_subtotal(D("120.00"), 1000) == D("120.00")


def test_rounding_is_half_up_not_bankers():
    assert calculate_subtotal(D("45.00"), 333) == D("14.99")   # 14.985 -> 14.99 (banker's gives .98)
    assert calculate_subtotal(D("35.00"), 1) == D("0.04")      # 0.035 -> 0.04
    assert calculate_subtotal(D("35.00"), 3) == D("0.11")      # 0.105 -> 0.11


def test_always_two_decimal_places():
    assert str(calculate_subtotal(D("60.00"), 1000)) == "60.00"
    assert str(calculate_subtotal(D("60.00"), 0)) == "0.00"
    assert str(calculate_total([])) == "0.00"


def test_total_is_sum_of_rounded_subtotals():
    lines = [calculate_subtotal(D("45.00"), 333), calculate_subtotal(D("45.00"), 333)]
    assert lines == [D("14.99"), D("14.99")]
    assert calculate_total(lines) == D("29.98")  # rounding the raw sum (29.97) would not match the lines


def test_negative_weight_rejected():
    with pytest.raises(ValueError):
        calculate_subtotal(D("60.00"), -1)


def test_money_helper():
    assert money(D("2.005")) == D("2.01")
    assert money(D("2.004")) == D("2.00")
