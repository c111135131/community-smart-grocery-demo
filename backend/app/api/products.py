"""Product endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.product import ProductOut
from app.services import product_service as svc

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)) -> list[ProductOut]:
    return svc.list_active_products(db)


@router.get("/{product_id}", response_model=ProductOut)
def read_product(product_id: int, db: Session = Depends(get_db)) -> ProductOut:
    try:
        return svc.get_active_product(db, product_id)
    except svc.ProductNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此商品") from None
