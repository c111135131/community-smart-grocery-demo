"""Product model. Weights are integer grams; prices are NUMERIC (never float)."""
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_grams >= 0", name="ck_products_stock_nonneg"),
        CheckConstraint(
            "min_weight_grams > 0 AND max_weight_grams >= min_weight_grams",
            name="ck_products_weight_bounds",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Integer code carried in the 16-byte IoT packet (uint16 range).
    product_code: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    price_per_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock_grams: Mapped[int] = mapped_column(Integer)
    # Plausible per-event weight bounds, used later by the gateway/cart checks.
    min_weight_grams: Mapped[int] = mapped_column(Integer)
    max_weight_grams: Mapped[int] = mapped_column(Integer)
    nutrition_json: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
