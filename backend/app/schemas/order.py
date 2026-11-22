"""Checkout and order schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.cart import CartOut


class CheckoutRequest(BaseModel):
    """Simulated payment outcome. No real payment integration exists."""

    payment_simulation: Literal["SUCCESS", "FAILURE"]


class OrderItemOut(BaseModel):
    """A line as it was at checkout time (snapshot of name and price)."""

    product_id: int
    product_name: str
    price_per_kg: Decimal
    weight_grams: int
    subtotal: Decimal


class CheckoutResult(BaseModel):
    order_id: int
    payment_status: Literal["PAID", "FAILED"]
    total_amount: Decimal
    items: list[OrderItemOut]
    message: str
    cart: CartOut  # empty after a PAID order; unchanged after FAILED


class AdminOrderOut(BaseModel):
    order_id: int
    resident_id: int
    resident_name: str
    total_amount: Decimal
    payment_status: Literal["PAID", "FAILED"]
    created_at: datetime
    items: list[OrderItemOut]
