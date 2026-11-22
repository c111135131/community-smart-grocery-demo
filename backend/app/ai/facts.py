"""The grounded facts handed to an LLM provider.

Everything a provider may say comes from this object, which the backend builds from
the database and the knowledge base. It deliberately contains NO prices, NO stock
quantities, NO resident name and NO card id.
"""
from dataclasses import dataclass, field

from app.ai.recommender import Recommendation
from app.schemas.nutrition import BasketItem


@dataclass(frozen=True)
class SnippetRef:
    id: str
    title: str
    text: str


@dataclass
class GroundedFacts:
    question: str
    preferences: list[str]
    allergies: list[str]
    recent_purchases: list[str]
    recommendation: Recommendation
    product_snippets: dict[int, SnippetRef] = field(default_factory=dict)  # product_code -> entry
    topic_snippets: list[SnippetRef] = field(default_factory=list)
    basket_items: list[BasketItem] | None = None

    @property
    def all_snippets(self) -> list[SnippetRef]:
        """Every snippet shown to the provider, unique, in a stable order."""
        seen: dict[str, SnippetRef] = {}
        codes = [p.product_code for p in self.recommendation.picks]
        codes += [m.product_code for m in self.recommendation.mentioned]
        for code in codes:
            ref = self.product_snippets.get(code)
            if ref:
                seen.setdefault(ref.id, ref)
        for ref in self.topic_snippets:
            seen.setdefault(ref.id, ref)
        return list(seen.values())
