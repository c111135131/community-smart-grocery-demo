"""Simulated checkout. The backend is the only authority for price, stock and payment state.

All of checkout runs in ONE database transaction:

  1. lock the resident's cart row, then the product rows in the cart (ordered by id, so
     two checkouts always lock in the same order and cannot deadlock)
  2. reject (409) an empty cart, a delisted product, or insufficient stock; nothing is
     written in that case
  3. price every line with services.pricing (never trust client or AI numbers)
  4. "payment": SUCCESS or FAILURE as requested (simulation only, no payment provider)
  5. SUCCESS -> order PAID + order items, stock decremented, cart emptied
     FAILURE -> order FAILED + order items (kept for the audit trail), stock untouched,
                cart preserved so the resident can retry
  6. commit; any error rolls everything back, so a PAID order, the stock decrement and
     the cart clearing either all happen or none do.

Inventory is therefore decremented only after a successful (simulated) payment.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cart, CartItem, Order, OrderItem, Product, Resident
from app.schemas.order import CheckoutResult, OrderItemOut
from app.services import cart_service, pricing
from app.services.resident_service import ResidentNotFoundError

PAYMENT_OK_MESSAGE = "模擬付款成功，訂單已建立並更新庫存"
PAYMENT_FAILED_MESSAGE = "模擬付款失敗，未扣庫存，購物車已保留，可重新結帳"


class CheckoutRejectionCode(StrEnum):
    EMPTY_CART = "EMPTY_CART"
    PRODUCT_UNAVAILABLE = "PRODUCT_UNAVAILABLE"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"


class CheckoutRejected(Exception):
    """The cart cannot be checked out (HTTP 409). Nothing was changed."""

    def __init__(self, code: CheckoutRejectionCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _Line:
    cart_item: CartItem
    product: Product
    subtotal: Decimal


def _decrement_stock(lines: list[_Line]) -> None:
    """Reduce stock for every line. Only called after payment succeeded."""
    for line in lines:
        line.product.stock_grams -= line.cart_item.weight_grams


def checkout(db: Session, resident_id: int, payment_simulation: str) -> CheckoutResult:
    if db.get(Resident, resident_id) is None:
        raise ResidentNotFoundError(resident_id)

    try:
        cart = db.scalar(select(Cart).where(Cart.resident_id == resident_id).with_for_update())
        rows = []
        if cart is not None:
            rows = db.execute(
                select(CartItem, Product)
                .join(Product, CartItem.product_id == Product.id)
                .where(CartItem.cart_id == cart.id)
                .order_by(Product.id)
                .with_for_update(of=Product)
            ).all()
        if not rows:
            raise CheckoutRejected(CheckoutRejectionCode.EMPTY_CART, "購物車是空的")

        lines: list[_Line] = []
        for cart_item, product in rows:
            if not product.is_active:
                raise CheckoutRejected(
                    CheckoutRejectionCode.PRODUCT_UNAVAILABLE,
                    f"{product.name} 已下架，請先從購物車移除",
                )
            if cart_item.weight_grams > product.stock_grams:
                raise CheckoutRejected(
                    CheckoutRejectionCode.INSUFFICIENT_STOCK,
                    f"{product.name} 庫存不足（購物車 {cart_item.weight_grams} 公克，"
                    f"庫存 {product.stock_grams} 公克）",
                )
            lines.append(
                _Line(
                    cart_item,
                    product,
                    pricing.calculate_subtotal(product.price_per_kg, cart_item.weight_grams),
                )
            )

        total = pricing.calculate_total(line.subtotal for line in lines)
        paid = payment_simulation == "SUCCESS"

        order = Order(
            resident_id=resident_id,
            total_amount=total,
            payment_status="PAID" if paid else "FAILED",
            items=[
                OrderItem(
                    product_id=line.product.id,
                    product_name_snapshot=line.product.name,
                    price_per_kg_snapshot=line.product.price_per_kg,
                    weight_grams=line.cart_item.weight_grams,
                    subtotal=line.subtotal,
                )
                for line in lines
            ],
        )
        db.add(order)
        db.flush()

        item_out = [
            OrderItemOut(
                product_id=line.product.id,
                product_name=line.product.name,
                price_per_kg=line.product.price_per_kg,
                weight_grams=line.cart_item.weight_grams,
                subtotal=line.subtotal,
            )
            for line in lines
        ]

        if paid:
            _decrement_stock(lines)
            for line in lines:
                db.delete(line.cart_item)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return CheckoutResult(
        order_id=order.id,
        payment_status="PAID" if paid else "FAILED",
        total_amount=total,
        items=item_out,
        message=PAYMENT_OK_MESSAGE if paid else PAYMENT_FAILED_MESSAGE,
        cart=cart_service.get_cart(db, resident_id),
    )
