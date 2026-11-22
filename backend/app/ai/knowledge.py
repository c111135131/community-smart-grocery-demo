"""Nutrition seed knowledge base loader.

The knowledge base is a small local JSON file (knowledge_base/nutrition_seed.json).
It is general, educational information written for this demo; it has NOT been
reviewed by a nutritionist and is not authoritative. Authoritative product facts
(prices, stock, nutrition numbers) always come from the database.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.core.config import get_settings


class KnowledgeEntry(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    product_codes: list[int] = Field(default_factory=list)


class KnowledgeBase(BaseModel):
    description: str = ""
    disclaimer: str = ""
    version: int = 1
    entries: list[KnowledgeEntry]

    @model_validator(mode="after")
    def ids_must_be_unique(self) -> "KnowledgeBase":
        ids = [e.id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("knowledge entry ids must be unique")
        return self


def load_knowledge_base(path: Path) -> KnowledgeBase:
    """Load and validate a knowledge base file (raises on malformed content)."""
    return KnowledgeBase.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_knowledge_base() -> KnowledgeBase:
    return load_knowledge_base(get_settings().knowledge_base_file)
