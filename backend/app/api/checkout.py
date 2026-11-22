"""Checkout endpoint (simulated payment)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.order import CheckoutRequest, CheckoutResult
from app.services import checkout_service
from app.services.resident_service import ResidentNotFoundError

router = APIRouter(prefix="/residents/{resident_id}/checkout", tags=["checkout"])


@router.post(
    "",
    response_model=CheckoutResult,
    responses={
        404: {"description": "Resident not found"},
        409: {"description": "Empty cart, delisted product or insufficient stock"},
    },
)
def checkout(
    resident_id: int, payload: CheckoutRequest, db: Session = Depends(get_db)
) -> CheckoutResult:
    """Simulated checkout.

    A failed simulated payment is a normal business outcome, so it returns HTTP 200 with
    `payment_status: "FAILED"` (cart kept, stock untouched). HTTP 409 means the cart
    could not be checked out at all.
    """
    try:
        return checkout_service.checkout(db, resident_id, payload.payment_simulation)
    except ResidentNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此居民") from None
    except checkout_service.CheckoutRejected as rej:
        raise HTTPException(status_code=409, detail=rej.message) from None
