"""Integration test with a REAL MCP client talking to the server over stdio."""
import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.tools import TOOL_DESCRIPTIONS, TOOL_NAMES
from app.models import Base
from app.seed import seed

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def db_url(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("mcp") / "mcp.db"
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        seed(s)
    engine.dispose()
    return url


def run_with_session(db_url: str, scenario):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "app.ai.mcp_server"],
        env={**os.environ, "DATABASE_URL": db_url}, cwd=BACKEND_DIR,
    )

    async def main():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await scenario(session)

    return asyncio.run(asyncio.wait_for(main(), timeout=90))


def test_server_lists_exactly_the_read_only_tools(db_url):
    async def scenario(session):
        return (await session.list_tools()).tools

    tools = run_with_session(db_url, scenario)
    assert {t.name for t in tools} == set(TOOL_NAMES)      # no drift from the in-app tool layer
    for t in tools:
        assert t.annotations.read_only_hint is True and t.annotations.destructive_hint is False
        assert t.description == TOOL_DESCRIPTIONS[t.name]


def test_tools_return_database_and_knowledge_facts(db_url):
    async def scenario(session):
        found = await session.call_tool("get_product_info", {"product_code": 101})
        missing = await session.call_tool("get_product_info", {"product_code": 999})
        fruit = await session.call_tool("get_inventory", {"in_stock_only": True, "category": "fruit"})
        kb = await session.call_tool("search_nutrition_knowledge", {"query": "低鈉", "limit": 2})
        return found, missing, fruit, kb

    found, missing, fruit, kb = run_with_session(db_url, scenario)
    assert found.structured_content["found"] is True
    assert found.structured_content["product"]["price_per_kg"] == "60.00"
    assert missing.structured_content == {"found": False, "product_code": 999}
    assert fruit.structured_content["count"] == 2
    assert [s["id"] for s in kb.structured_content["snippets"]][0] == "nutrition_seed_001"


def test_write_style_tools_do_not_exist(db_url):
    async def scenario(session):
        out = []
        for name in ["update_stock", "checkout", "set_price"]:
            try:
                r = await session.call_tool(name, {})
                out.append(bool(r.is_error))
            except Exception:
                out.append(True)
        return out

    assert run_with_session(db_url, scenario) == [True, True, True]
