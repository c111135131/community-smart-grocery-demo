"""FastAPI application entry point."""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, cart, checkout, health, nutrition, products, residents
from app.core.config import get_settings

app = FastAPI(
    title="Community Smart Grocery API",
    description="Course-project prototype (educational demo, not production).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(residents.router)
api_v1.include_router(products.router)
api_v1.include_router(cart.router)
api_v1.include_router(checkout.router)
api_v1.include_router(nutrition.router)
api_v1.include_router(admin.router)
app.include_router(api_v1)
