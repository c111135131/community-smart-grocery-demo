"""Product queries. Prices and stock always come from the database."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.schemas.product import ProductOut


class ProductNotFoundError(Exception):
    """No (active) product with the given ID."""


def _to_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        product_code=p.product_code,
        name=p.name,
        category=p.category,
        price_per_kg=p.price_per_kg,
        stock_grams=p.stock_grams,
        min_weight_grams=p.min_weight_grams,
        max_weight_grams=p.max_weight_grams,
        nutrition=p.nutrition_json or {},
        is_active=p.is_active,
    )


def list_active_products(db: Session) -> list[ProductOut]:
    rows = db.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.product_code)
    )
    return [_to_out(p) for p in rows]


def get_active_product(db: Session, product_id: int) -> ProductOut:
    p = db.get(Product, product_id)
    if p is None or not p.is_active:
        raise ProductNotFoundError(product_id)
    return _to_out(p)


def list_inventory(db: Session) -> list[ProductOut]:
    """Admin view: every product including inactive ones."""
    rows = db.scalars(select(Product).order_by(Product.product_code))
    return [_to_out(p) for p in rows]
