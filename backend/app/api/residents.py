"""Resident endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.resident import LoginRequest, ResidentOut
from app.services import resident_service as svc

router = APIRouter(prefix="/residents", tags=["residents"])


@router.post("/login", response_model=ResidentOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> ResidentOut:
    try:
        return svc.login_with_card(db, payload.card_id)
    except svc.UnknownCardError:
        raise HTTPException(status_code=401, detail="找不到此識別卡，請確認卡號") from None


@router.get("/{resident_id}", response_model=ResidentOut)
def read_resident(resident_id: int, db: Session = Depends(get_db)) -> ResidentOut:
    try:
        return svc.get_resident(db, resident_id)
    except svc.ResidentNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此居民") from None
