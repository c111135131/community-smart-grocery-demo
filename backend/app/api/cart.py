"""Cart and IoT event endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Resident
from app.schemas.cart import CartOut
from app.schemas.iot import CartEventRequest, CartEventResult, RawPacketRequest, RemoveItemResult
from app.services import cart_service, iot_service
from app.services.resident_service import ResidentNotFoundError

router = APIRouter(prefix="/residents/{resident_id}/cart", tags=["cart"])

# Rejection code -> HTTP status (docs/API_SPEC.md section 7).
_STATUS_BY_CODE: dict[str, int] = {
    "INVALID_LENGTH": 400,
    "INVALID_HEADER": 400,
    "UNSUPPORTED_COMMAND": 400,
    "CHECK_CODE_MISMATCH": 400,
    "UNKNOWN_DEVICE": 400,
    "INVALID_FIELDS": 400,
    "WEIGHT_OUT_OF_RANGE": 400,
    "SEQUENCE_REPLAY": 409,
    "INSUFFICIENT_STOCK": 409,
    "ITEM_NOT_IN_CART": 409,
    "REMOVE_EXCEEDS_CART": 409,
    "PRODUCT_NOT_FOUND": 404,
}

# Rejected events still return the full result body (validation steps, packet hex, cart)
# so the UI can show *why*; only the status code differs.
_EVENT_RESPONSES = {
    400: {"model": CartEventResult, "description": "Invalid or unsupported packet"},
    404: {"description": "Resident/device/product not found"},
    409: {"model": CartEventResult, "description": "Replayed sequence or invalid cart state"},
}


def _status_for(result: CartEventResult, response: Response) -> CartEventResult:
    if not result.accepted:
        response.status_code = _STATUS_BY_CODE.get(result.rejection_code or "", 400)
    return result


@router.get("", response_model=CartOut)
def read_cart(resident_id: int, db: Session = Depends(get_db)) -> CartOut:
    if db.get(Resident, resident_id) is None:
        raise HTTPException(status_code=404, detail="找不到此居民")
    return cart_service.get_cart(db, resident_id)


@router.post("/events", response_model=CartEventResult, responses=_EVENT_RESPONSES)
def post_event(
    resident_id: int,
    payload: CartEventRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> CartEventResult:
    """Simulate a device event; the backend encodes it into the 16-byte packet."""
    try:
        result = iot_service.submit_simulated_event(db, resident_id, payload)
    except ResidentNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此居民") from None
    except iot_service.DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此裝置") from None
    except iot_service.SequenceExhaustedError:
        raise HTTPException(status_code=409, detail="裝置序號已用盡（示範未實作序號回捲）") from None
    return _status_for(result, response)


@router.post("/packets", response_model=CartEventResult, responses=_EVENT_RESPONSES)
def post_raw_packet(
    resident_id: int,
    payload: RawPacketRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> CartEventResult:
    """Demo helper: send a raw hex frame (e.g. a replayed or tampered packet) to the gateway."""
    try:
        result = iot_service.submit_raw_packet(db, resident_id, payload.packet_hex)
    except ResidentNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此居民") from None
    return _status_for(result, response)


@router.delete(
    "/items/{product_id}",
    response_model=RemoveItemResult,
    responses={
        404: {"description": "Resident, device or product not found"},
        409: {"model": RemoveItemResult, "description": "Product not in cart or packet rejected"},
    },
)
def remove_item(
    resident_id: int,
    product_id: int,
    response: Response,
    device_id: int = Query(default=1, ge=0, le=0xFFFF, description="Simulated device sending the packets"),
    db: Session = Depends(get_db),
) -> RemoveItemResult:
    """Remove a product line from the cart via REMOVE_ITEM packets through the Gateway."""
    try:
        events = iot_service.remove_cart_item(db, resident_id, product_id, device_id)
    except ResidentNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此居民") from None
    except iot_service.ProductNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此商品") from None
    except iot_service.ItemNotInCartError:
        raise HTTPException(status_code=409, detail="購物車內沒有此商品") from None
    except iot_service.DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此裝置") from None
    except iot_service.SequenceExhaustedError:
        raise HTTPException(status_code=409, detail="裝置序號已用盡（示範未實作序號回捲）") from None

    last = events[-1]
    if not last.accepted:
        response.status_code = _STATUS_BY_CODE.get(last.rejection_code or "", 400)
    return RemoveItemResult(accepted=last.accepted, events=events, cart=last.cart)
