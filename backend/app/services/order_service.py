"""Read-only order queries (administrator view)."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, Resident
from app.schemas.order import AdminOrderOut, OrderItemOut


def list_recent_orders(db: Session, limit: int = 20) -> list[AdminOrderOut]:
    """Newest first. FAILED orders are included so failed payments can be audited."""
    orders = db.scalars(
        select(Order).options(selectinload(Order.items)).order_by(Order.id.desc()).limit(limit)
    ).all()
    names = {
        r.id: r.display_name
        for r in db.scalars(select(Resident).where(Resident.id.in_({o.resident_id for o in orders})))
    }
    return [
        AdminOrderOut(
            order_id=o.id,
            resident_id=o.resident_id,
            resident_name=names.get(o.resident_id, "?"),
            total_amount=o.total_amount,
            payment_status=o.payment_status,  # type: ignore[arg-type]
            created_at=o.created_at,
            items=[
                OrderItemOut(
                    product_id=i.product_id,
                    product_name=i.product_name_snapshot,
                    price_per_kg=i.price_per_kg_snapshot,
                    weight_grams=i.weight_grams,
                    subtotal=i.subtotal,
                )
                for i in sorted(o.items, key=lambda x: x.id)
            ],
        )
        for o in orders
    ]
