"""Nutrition assistant agent: resident context -> read-only tools -> recommendation -> prose.

Flow for one question:

  1. load the resident's preferences, allergies and recent PAID purchases (read-only)
  2. guardrail: transactional requests ("check out for me", "change the price") are
     refused without calling any model
  3. call the read-only tools (inventory, product info, nutrition-knowledge search)
  4. app.ai.recommender picks and explains products deterministically
  5. a provider (mock by default) phrases the grounded facts; if a real provider fails
     we fall back to the mock provider and say so in `notice`
  6. return the answer with the knowledge ids the provider was actually given

The agent has no write path: it only reads, and the tools it can call are read-only.
"""
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.facts import GroundedFacts, SnippetRef
from app.ai.providers import (
    LLMRequest,
    MockProvider,
    ProviderError,
    ProviderSelection,
    build_prompt,
)
from app.ai.recommender import MAX_PICKS, mentioned_products, recommend
from app.ai.retriever import Retriever
from app.ai.tools import ToolBox, ToolRunner
from app.models import Order, OrderItem, Resident
from app.schemas.nutrition import (
    NutritionResponse,
    RecommendedProductOut,
    SourceSnippetOut,
    ToolCallOut,
)
from app.services.resident_service import ResidentNotFoundError

logger = logging.getLogger(__name__)

DISCLAIMER = "※ 以上為一般飲食資訊，不是醫療建議；價格、庫存與付款請以商店系統顯示為準。"
GUARDRAIL_ANSWER = (
    "我是營養資訊助理，只能提供一般飲食資訊，無法執行結帳、付款、退款，"
    "也無法修改價格、庫存、購物車或訂單。這些操作請使用購物車與結帳功能，由系統處理。\n"
    "如果想了解食材的營養，可以直接問我，例如「請推薦適合我的低鈉食材」。"
)
MAX_ANSWER_CHARS = 4000
RECENT_ORDERS = 3

# Requests to perform a transaction or change business data. The assistant cannot do
# these anyway (it has no write tools); this just answers clearly instead of guessing.
_TRANSACTION_PATTERNS = [
    re.compile(r"(幫我|替我|請幫我|請你|麻煩|直接).{0,8}(結帳|付款|付錢|下單|退款|加入購物車|放入購物車|扣庫存)"),
    re.compile(r"(修改|更改|調整|更新|刪除|清空|改成|設為|設定).{0,10}(價格|售價|單價|庫存|訂單|購物車|付款)"),
    re.compile(r"(把|將).{0,12}(價格|售價|單價|庫存).{0,10}(改|設|調|降|提高)"),
    re.compile(r"\b(check\s?out|refund|set (the )?price|change (the )?price|delete (the )?order)\b", re.I),
]


def is_transaction_request(question: str) -> bool:
    return any(p.search(question) for p in _TRANSACTION_PATTERNS)


class NutritionAgent:
    def __init__(self, db: Session, retriever: Retriever, selection: ProviderSelection) -> None:
        self._db = db
        self._retriever = retriever
        self._selection = selection

    # -- resident context (privacy: name and card id are never used here) ----------
    def _load_context(self, resident_id: int) -> tuple[list[str], list[str], list[str]]:
        resident = self._db.scalar(
            select(Resident).options(joinedload(Resident.health_profile)).where(Resident.id == resident_id)
        )
        if resident is None:
            raise ResidentNotFoundError(resident_id)
        profile = resident.health_profile
        prefs = [str(x) for x in (profile.dietary_preferences if profile else [])]
        allergies = [str(x) for x in (profile.allergies if profile else [])]

        order_ids = list(self._db.scalars(
            select(Order.id)
            .where(Order.resident_id == resident_id, Order.payment_status == "PAID")
            .order_by(Order.id.desc()).limit(RECENT_ORDERS)
        ))
        recent: list[str] = []
        if order_ids:
            rows = self._db.execute(
                select(OrderItem.product_name_snapshot)
                .where(OrderItem.order_id.in_(order_ids))
                .order_by(OrderItem.order_id.desc(), OrderItem.id)
            )
            for (name,) in rows:
                if name not in recent:
                    recent.append(name)
        return prefs, allergies, recent

    def answer(self, resident_id: int, question: str) -> NutritionResponse:
        prefs, allergies, recent = self._load_context(resident_id)

        if is_transaction_request(question):
            return NutritionResponse(
                answer=GUARDRAIL_ANSWER, sources=[], provider="guardrail", notice=None,
                used_preferences=prefs, recommended_products=[], source_details=[], tool_calls=[],
            )

        runner = ToolRunner(ToolBox(self._db, self._retriever))

        inventory = runner.call("get_inventory", in_stock_only=False)
        mentioned = []
        for p in mentioned_products(question, inventory):
            fact = runner.call("get_product_info", product_code=p.product_code)
            if fact is not None:
                mentioned.append(fact)
        rec = recommend(question, prefs, inventory, mentioned)

        tags = list(dict.fromkeys(
            [*prefs, rec.focus.knowledge_tag, *(["allergy"] if allergies else [])]
        ))
        topic_hits = [
            h for h in runner.call("search_nutrition_knowledge", query=question, limit=6, tags=tags)
            if "product" not in h.tags  # product entries are attached only to picked/mentioned products
        ][:3]
        product_snippets: dict[int, SnippetRef] = {}
        wanted = [(p.product_code, p.name) for p in rec.picks]
        wanted += [(m.product_code, m.name) for m in rec.mentioned if m.product_code not in dict(wanted)]
        if wanted:
            hits = runner.call(
                "search_nutrition_knowledge",
                query=" ".join(name for _, name in wanted), limit=MAX_PICKS * 2, tags=["product"],
            )
            for code, _ in wanted:
                for h in hits:
                    if "product" in h.tags and code in h.product_codes:
                        product_snippets[code] = SnippetRef(h.id, h.title, h.text)
                        break

        facts = GroundedFacts(
            question=question, preferences=prefs, allergies=allergies, recent_purchases=recent,
            recommendation=rec, product_snippets=product_snippets,
            topic_snippets=[SnippetRef(h.id, h.title, h.text) for h in topic_hits],
        )

        system, user = build_prompt(facts)
        request = LLMRequest(system, user, facts)
        provider, notice = self._selection.provider, self._selection.notice
        try:
            text = provider.generate(request)
        except ProviderError as exc:
            logger.warning("LLM provider %s failed: %s", provider.name, exc)
            notice = f"外部 LLM（{provider.name}）呼叫失敗（{exc}），已改用 mock 提供者。"
            provider = MockProvider()
            text = provider.generate(request)

        snippets = facts.all_snippets
        return NutritionResponse(
            answer=f"{text.strip()[:MAX_ANSWER_CHARS]}\n\n{DISCLAIMER}",
            sources=[s.id for s in snippets],
            provider=provider.name,
            notice=notice,
            used_preferences=prefs,
            recommended_products=[
                RecommendedProductOut(product_code=p.product_code, name=p.name, reasons=p.reasons)
                for p in rec.picks
            ],
            source_details=[SourceSnippetOut(id=s.id, title=s.title, text=s.text) for s in snippets],
            tool_calls=[ToolCallOut(name=t.name, arguments=t.arguments, result_count=t.result_count)
                        for t in runner.traces],
        )
