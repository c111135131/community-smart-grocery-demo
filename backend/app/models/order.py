"""Order tables. Schema only in Phase 1; checkout logic arrives in Phase 3."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("payment_status IN ('PAID', 'FAILED')", name="ck_orders_payment_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    payment_status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    # Snapshots keep historical orders correct even if the product changes later.
    product_name_snapshot: Mapped[str] = mapped_column(String(64))
    price_per_kg_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    weight_grams: Mapped[int] = mapped_column(Integer)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
