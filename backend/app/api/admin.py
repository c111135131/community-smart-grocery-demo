"""Administrator endpoints.

Demo only: there is intentionally no admin authentication (see CLAUDE.md).
Read-only views of inventory, orders and the IoT audit trail.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.iot import DeviceOut, IotEventOut
from app.schemas.order import AdminOrderOut
from app.schemas.product import ProductOut
from app.services import iot_service, order_service
from app.services import product_service as svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/inventory", response_model=list[ProductOut])
def inventory(db: Session = Depends(get_db)) -> list[ProductOut]:
    return svc.list_inventory(db)


@router.get("/iot-events", response_model=list[IotEventOut])
def iot_events(
    limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)
) -> list[IotEventOut]:
    """Audit trail of every frame the gateway received (newest first)."""
    return iot_service.list_iot_events(db, limit)


@router.get("/devices", response_model=list[DeviceOut])
def devices(db: Session = Depends(get_db)) -> list[DeviceOut]:
    """Device sequence state used for replay detection."""
    return iot_service.list_devices(db)


@router.get("/orders", response_model=list[AdminOrderOut])
def orders(
    limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)
) -> list[AdminOrderOut]:
    """Recent orders, newest first (PAID and FAILED)."""
    return order_service.list_recent_orders(db, limit)
