"""Product response schema. Prices are serialized as strings (e.g. "45.00") to avoid float error."""
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_code: int
    name: str
    category: str
    price_per_kg: Decimal
    stock_grams: int
    min_weight_grams: int
    max_weight_grams: int
    nutrition: dict[str, Any]
    is_active: bool
