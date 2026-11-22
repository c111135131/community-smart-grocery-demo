"""MCP server exposing the read-only tool layer to external MCP clients.

Run (stdio transport):

    cd backend && python -m app.ai.mcp_server

It publishes exactly the three tools in `app.ai.tools.TOOL_NAMES`, all read-only, backed
by the same `ToolBox` the in-app nutrition agent uses. There are no write tools, no
resident data and no authentication: it is a local demo server meant to be launched by a
trusted MCP client over stdio (never expose it on a network).

stdout carries the MCP protocol, so nothing in here may print to stdout.
"""
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.ai.tools import TOOL_DESCRIPTIONS, ToolBox, default_retriever
from app.core.database import get_session_factory

server = MCPServer(
    "community-smart-grocery",
    instructions=(
        "Read-only tools for a community grocery demo: product facts, inventory and a small "
        "nutrition knowledge base. These tools cannot change prices, stock, carts or orders."
    ),
)

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def _toolbox_call(method: str, **kwargs: Any) -> Any:
    """Open a short-lived DB session, run one read-only tool, and close it."""
    with get_session_factory()() as db:
        return getattr(ToolBox(db, default_retriever()), method)(**kwargs)


@server.tool(name="get_product_info", description=TOOL_DESCRIPTIONS["get_product_info"],
             annotations=_READ_ONLY)
def get_product_info(product_code: int) -> dict[str, Any]:
    product = _toolbox_call("get_product_info", product_code=product_code)
    if product is None:
        return {"found": False, "product_code": product_code}
    return {"found": True, "product": product.model_dump(mode="json")}


@server.tool(name="get_inventory", description=TOOL_DESCRIPTIONS["get_inventory"],
             annotations=_READ_ONLY)
def get_inventory(in_stock_only: bool = True, category: str | None = None) -> dict[str, Any]:
    items = _toolbox_call("get_inventory", in_stock_only=in_stock_only, category=category)
    return {"count": len(items), "products": [p.model_dump(mode="json") for p in items]}


@server.tool(name="search_nutrition_knowledge",
             description=TOOL_DESCRIPTIONS["search_nutrition_knowledge"], annotations=_READ_ONLY)
def search_nutrition_knowledge(
    query: str, limit: int = 3, tags: list[str] | None = None
) -> dict[str, Any]:
    hits = _toolbox_call("search_nutrition_knowledge", query=query, limit=limit, tags=tags)
    return {"count": len(hits), "snippets": [h.model_dump(mode="json") for h in hits]}


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
