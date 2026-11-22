"""Nutrition assistant endpoint (read-only; never changes carts, orders, prices or stock)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.agent import NutritionAgent
from app.ai.providers import ProviderSelection, select_provider
from app.ai.retriever import Retriever
from app.ai.tools import default_retriever
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.nutrition import NutritionRequest, NutritionResponse
from app.services.resident_service import ResidentNotFoundError

router = APIRouter(prefix="/residents/{resident_id}/nutrition", tags=["nutrition"])


def get_provider_selection() -> ProviderSelection:
    """Dependency (overridable in tests): the configured provider, mock by default."""
    return select_provider(get_settings())


def get_retriever() -> Retriever:
    return default_retriever()


@router.post("/recommendations", response_model=NutritionResponse)
def recommend(
    resident_id: int,
    payload: NutritionRequest,
    db: Session = Depends(get_db),
    selection: ProviderSelection = Depends(get_provider_selection),
    retriever: Retriever = Depends(get_retriever),
) -> NutritionResponse:
    """Answer a nutrition question using the resident's preferences, retrieved knowledge
    and product facts. Works without any API key (mock provider)."""
    try:
        return NutritionAgent(db, retriever, selection).answer(resident_id, payload.question)
    except ResidentNotFoundError:
        raise HTTPException(status_code=404, detail="找不到此居民") from None
