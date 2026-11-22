"""Database engine, session factory and helpers."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping avoids stale connections; short timeout keeps /health snappy.
    url = get_settings().database_url
    # SQLite (optional local fallback, also used by the MCP integration test) has no
    # connect_timeout option.
    connect_args = {} if url.startswith("sqlite") else {"connect_timeout": 3}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool:
    """Return True if PostgreSQL answers a trivial query, else False."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - never leak DB errors/secrets to clients
        return False
