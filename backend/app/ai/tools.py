"""Read-only tool layer shared by the in-app agent and the MCP server.

Three tools only, and none of them can change anything:

    get_product_info(product_code)
    get_inventory(in_stock_only, category)
    search_nutrition_knowledge(query, limit, tags)

They never write, flush or commit; prices, stock and nutrition values are returned
exactly as stored (the AI layer must never calculate authoritative prices or change
inventory, see CLAUDE.md). The same `ToolBox` class backs `app.ai.mcp_server`, so the
tools an external MCP client sees are the tools the in-app agent uses.
"""
import inspect
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.knowledge import get_knowledge_base
from app.ai.retriever import KeywordRetriever, Retriever
from app.models import Product

MAX_QUERY_CHARS = 500
MAX_LIMIT = 10


class ProductFact(BaseModel):
    product_code: int
    name: str
    category: str
    price_per_kg: Decimal  # as stored; serialized as a string, never recalculated here
    stock_grams: int
    in_stock: bool
    nutrition: dict[str, Any]


class SnippetFact(BaseModel):
    id: str
    title: str
    text: str
    tags: list[str]
    product_codes: list[int]
    score: float


@lru_cache
def default_retriever() -> Retriever:
    return KeywordRetriever(get_knowledge_base().entries)


def _fact(p: Product) -> ProductFact:
    return ProductFact(
        product_code=p.product_code,
        name=p.name,
        category=p.category,
        price_per_kg=p.price_per_kg,
        stock_grams=p.stock_grams,
        in_stock=p.stock_grams > 0,
        nutrition=p.nutrition_json or {},
    )


class ToolBox:
    """The read-only tools. Method docstrings double as the MCP tool descriptions."""

    def __init__(self, db: Session, retriever: Retriever) -> None:
        self._db = db
        self._retriever = retriever

    def get_product_info(self, product_code: int) -> ProductFact | None:
        """Get one active product by its integer product code: name, category, price per kg, stock in grams and nutrition facts. Returns nothing if the code is unknown or the product is delisted. Read-only."""
        if not 0 <= product_code <= 0xFFFF:
            return None
        p = self._db.scalar(
            select(Product).where(Product.product_code == product_code, Product.is_active.is_(True))
        )
        return _fact(p) if p else None

    def get_inventory(
        self, in_stock_only: bool = True, category: str | None = None
    ) -> list[ProductFact]:
        """List active products with stock in grams and nutrition facts, optionally only those in stock and/or of one category (e.g. vegetable, fruit, root). Read-only."""
        query = select(Product).where(Product.is_active.is_(True)).order_by(Product.product_code)
        if in_stock_only:
            query = query.where(Product.stock_grams > 0)
        if category:
            query = query.where(Product.category == category)
        return [_fact(p) for p in self._db.scalars(query)]

    def search_nutrition_knowledge(
        self, query: str, limit: int = 3, tags: list[str] | None = None
    ) -> list[SnippetFact]:
        """Search the local nutrition knowledge base (RAG) and return the best matching snippets with their knowledge ids, most relevant first. Optional tags such as low_sodium or vegetarian boost matching entries. Read-only."""
        limit = max(1, min(int(limit), MAX_LIMIT))
        hits = self._retriever.search(query[:MAX_QUERY_CHARS], tags=tags or (), limit=limit)
        return [
            SnippetFact(
                id=h.id, title=h.title, text=h.text, tags=list(h.tags),
                product_codes=list(h.product_codes), score=h.score,
            )
            for h in hits
        ]


#: The complete list of tools. Anything not listed here cannot be called.
TOOL_NAMES: tuple[str, ...] = ("get_product_info", "get_inventory", "search_nutrition_knowledge")
TOOL_DESCRIPTIONS: dict[str, str] = {
    name: inspect.getdoc(getattr(ToolBox, name)) or "" for name in TOOL_NAMES
}


@dataclass
class ToolCallTrace:
    name: str
    arguments: dict[str, Any]
    result_count: int


@dataclass
class ToolRunner:
    """Calls tools by name and records a trace of every call (shown in the API/UI)."""

    toolbox: ToolBox
    traces: list[ToolCallTrace] = field(default_factory=list)

    def call(self, name: str, **arguments: Any) -> Any:
        if name not in TOOL_NAMES:
            raise ValueError(f"unknown tool: {name}")  # no write tools exist to be tricked into
        result = getattr(self.toolbox, name)(**arguments)
        count = len(result) if isinstance(result, list) else (0 if result is None else 1)
        self.traces.append(ToolCallTrace(name, dict(arguments), count))
        return result
