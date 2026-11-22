"""Cart business logic.

Phase 2: applies validated IoT events to the cart (weights only). Server-side
pricing, totals and the remove-item API flow are Phase 3. The cart is only ever
changed by events that already passed the gateway.
"""
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gateway.events import NormalizedIoTEvent
from app.gateway.packet import Command
from app.models import Cart, CartItem, Product
from app.schemas.cart import CartItemOut, CartOut
from app.services import pricing


class CartRejectionCode(StrEnum):
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    WEIGHT_OUT_OF_RANGE = "WEIGHT_OUT_OF_RANGE"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    ITEM_NOT_IN_CART = "ITEM_NOT_IN_CART"
    REMOVE_EXCEEDS_CART = "REMOVE_EXCEEDS_CART"


class CartRejection(Exception):
    """The event was authentic but the cart cannot apply it. Cart is left unchanged."""

    def __init__(self, code: CartRejectionCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def get_cart(db: Session, resident_id: int) -> CartOut:
    rows = db.execute(
        select(CartItem, Product)
        .join(Cart, CartItem.cart_id == Cart.id)
        .join(Product, CartItem.product_id == Product.id)
        .where(Cart.resident_id == resident_id)
        .order_by(Product.product_code)
    ).all()
    items = [
        CartItemOut(
            product_id=p.id,
            product_code=p.product_code,
            name=p.name,
            weight_grams=ci.weight_grams,
            price_per_kg=p.price_per_kg,
            subtotal=pricing.calculate_subtotal(p.price_per_kg, ci.weight_grams),
        )
        for ci, p in rows
    ]
    return CartOut(
        items=items,
        total_weight_grams=sum(i.weight_grams for i in items),
        total_amount=pricing.calculate_total(i.subtotal for i in items),
    )


def apply_event(db: Session, resident_id: int, event: NormalizedIoTEvent) -> None:
    """Apply an ADD_ITEM / REMOVE_ITEM event. All checks run BEFORE any change,
    so a rejection never leaves the cart partially modified.

    Rules:
    - ADD_ITEM needs an active product, a weight within the product's per-event range
      (min..max) and must not push the cart above the stock on hand.
    - REMOVE_ITEM subtracts the given weight. Only the per-event MAX applies (the minimum
      would make a small remainder, e.g. 30 g, impossible to ever remove). Removing a
      product that is not in the cart, or more than it holds, is rejected; removing
      exactly the remaining weight deletes the line. Inactive products can still be
      removed so a cart never gets stuck on a delisted product.
    """
    if event.command not in (Command.ADD_ITEM, Command.REMOVE_ITEM):
        raise ValueError(f"cart cannot apply command {event.command.name}")
    is_add = event.command == Command.ADD_ITEM

    query = select(Product).where(Product.product_code == event.product_code)
    if is_add:
        query = query.where(Product.is_active.is_(True))
    product = db.scalar(query)
    if product is None:
        raise CartRejection(
            CartRejectionCode.PRODUCT_NOT_FOUND, f"unknown product code {event.product_code}"
        )
    too_light = is_add and event.weight_grams < product.min_weight_grams
    if too_light or event.weight_grams > product.max_weight_grams:
        allowed = (
            f"{product.min_weight_grams}-{product.max_weight_grams} g"
            if is_add
            else f"at most {product.max_weight_grams} g"
        )
        raise CartRejection(
            CartRejectionCode.WEIGHT_OUT_OF_RANGE,
            f"{product.name}: weight {event.weight_grams} g outside allowed {allowed} per event",
        )

    # Row lock: serializes with a concurrent checkout of the same cart (no-op on SQLite).
    cart = db.scalar(select(Cart).where(Cart.resident_id == resident_id).with_for_update())
    item = None
    if cart is not None:
        item = db.scalar(
            select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
        )
    current = item.weight_grams if item else 0

    if is_add:
        new_total = current + event.weight_grams
        if new_total > product.stock_grams:
            raise CartRejection(
                CartRejectionCode.INSUFFICIENT_STOCK,
                f"{product.name}: cart would hold {new_total} g but only "
                f"{product.stock_grams} g in stock",
            )
        if cart is None:
            cart = Cart(resident_id=resident_id)
            db.add(cart)
            db.flush()
        if item is None:
            db.add(CartItem(cart_id=cart.id, product_id=product.id, weight_grams=new_total))
        else:
            item.weight_grams = new_total
    else:
        if item is None:
            raise CartRejection(
                CartRejectionCode.ITEM_NOT_IN_CART, f"{product.name} is not in the cart"
            )
        if event.weight_grams > current:
            raise CartRejection(
                CartRejectionCode.REMOVE_EXCEEDS_CART,
                f"{product.name}: cannot remove {event.weight_grams} g, cart has {current} g",
            )
        if event.weight_grams == current:
            db.delete(item)
        else:
            item.weight_grams = current - event.weight_grams

    assert cart is not None
    cart.updated_at = datetime.now(UTC)
