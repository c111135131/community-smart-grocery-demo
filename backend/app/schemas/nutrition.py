"""Nutrition assistant request/response schemas."""
from typing import Any

from pydantic import BaseModel, Field, field_validator


class NutritionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500, examples=["請推薦適合我的低鈉食材"])

    @field_validator("question")
    @classmethod
    def strip_and_require(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be blank")
        return v


class SourceSnippetOut(BaseModel):
    """A knowledge snippet the answer was grounded on (its id appears in `sources`)."""

    id: str
    title: str
    text: str


class RecommendedProductOut(BaseModel):
    product_code: int
    name: str
    reasons: list[str]


class ToolCallOut(BaseModel):
    """One read-only tool call made while answering (transparency for the demo)."""

    name: str
    arguments: dict[str, Any]
    result_count: int


class NutritionResponse(BaseModel):
    answer: str
    sources: list[str]  # knowledge ids actually given to the provider
    provider: str  # "mock", "anthropic" or "guardrail" (no model was called)
    notice: str | None  # why a different provider than configured was used, if so
    used_preferences: list[str]
    recommended_products: list[RecommendedProductOut]
    source_details: list[SourceSnippetOut]
    tool_calls: list[ToolCallOut]
