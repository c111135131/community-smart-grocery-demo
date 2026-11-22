"""Health-check endpoint."""
from fastapi import APIRouter

from app.core.database import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Always 200 when the API process is alive.

    `database` reports PostgreSQL connectivity separately so the API can start
    (and be diagnosed) even if the database container is not up yet.
    """
    return {
        "status": "ok",
        "service": "community-smart-grocery-backend",
        "database": "ok" if check_database() else "unavailable",
    }
