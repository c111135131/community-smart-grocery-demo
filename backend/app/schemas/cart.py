"""Cart schemas. Money is Decimal, serialized as a string such as "19.20"."""
from decimal import Decimal

from pydantic import BaseModel


class CartItemOut(BaseModel):
    product_id: int
    product_code: int
    name: str
    weight_grams: int
    price_per_kg: Decimal
    subtotal: Decimal  # computed by the backend


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_weight_grams: int
    total_amount: Decimal  # sum of the rounded line subtotals
