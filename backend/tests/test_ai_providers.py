import json

import httpx
import pytest

from app.ai.facts import GroundedFacts, SnippetRef
from app.ai.providers import (
    ANTHROPIC_URL, SYSTEM_PROMPT, AnthropicProvider, LLMRequest, MockProvider,
    ProviderError, build_prompt, select_provider,
)
from app.ai.recommender import recommend
from app.ai.retriever import KeywordRetriever
from app.ai.knowledge import get_knowledge_base
from app.ai.tools import ToolBox
from app.core.config import Settings

PRICES = ["60.00", "90.00", "80.00", "45.00", "55.00", "35.00", "70.00", "120.00"]


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


@pytest.fixture()
def facts(db_session) -> GroundedFacts:
    inv = ToolBox(db_session, KeywordRetriever(get_knowledge_base().entries)).get_inventory(False)
    rec = recommend("請推薦適合我的低鈉食材", ["low_sodium"], inv, [])
    return GroundedFacts(
        question="請推薦適合我的低鈉食材", preferences=["low_sodium"], allergies=["peanut"],
        recent_purchases=["番茄"], recommendation=rec,
        product_snippets={rec.picks[0].product_code: SnippetRef("nutrition_seed_013", "香蕉", "香蕉含鉀。")},
        topic_snippets=[SnippetRef("nutrition_seed_001", "低鈉", "低鈉說明。")],
    )


# ------------------------------------------------------------------ selection
def test_default_is_mock_without_any_key():
    sel = select_provider(settings())
    assert isinstance(sel.provider, MockProvider) and sel.notice is None


@pytest.mark.parametrize("value", ["", "mock", "MOCK", " Mock "])
def test_mock_spellings(value):
    assert select_provider(settings(ai_provider=value)).provider.name == "mock"


@pytest.mark.parametrize("kw,needle", [
    ({"ai_provider": "anthropic"}, "ANTHROPIC_API_KEY"),
    ({"ai_provider": "anthropic", "anthropic_api_key": "k"}, "AI_MODEL"),
    ({"ai_provider": "anthropic", "ai_model": "m"}, "ANTHROPIC_API_KEY"),
    ({"ai_provider": "gpt-17"}, "gpt-17"),
])
def test_incomplete_or_unknown_config_falls_back_to_mock_with_notice(kw, needle):
    sel = select_provider(settings(**kw))
    assert sel.provider.name == "mock" and needle in sel.notice


def test_complete_config_selects_anthropic_without_leaking_the_key():
    sel = select_provider(settings(ai_provider="anthropic", anthropic_api_key="sk-secret", ai_model="m"))
    assert sel.provider.name == "anthropic" and sel.notice is None
    assert "sk-secret" not in repr(sel.provider.__dict__.get("_model", "")) + str(sel.notice)


# ------------------------------------------------------------------ mock
def test_mock_is_deterministic_and_grounded(facts):
    req = LLMRequest(*build_prompt(facts), facts)
    a, b = MockProvider().generate(req), MockProvider().generate(req)
    assert a == b
    assert "低鈉" in a and "[nutrition_seed_001]" in a and "[nutrition_seed_013]" in a
    assert "花生" in a and "沒有過敏原資訊" in a and "番茄" in a  # allergy honesty + recent purchase
    assert "NT$" not in a and not any(p in a for p in PRICES)


# ------------------------------------------------------------------ prompt
def test_prompt_contains_only_grounded_facts_and_marks_question_untrusted(facts):
    system, user = build_prompt(facts)
    payload = json.loads(user)
    assert payload["resident_question"] == facts.question          # question is data, inside JSON
    assert {s["snippet_id"] for s in payload["knowledge_snippets"]} == {"nutrition_seed_013", "nutrition_seed_001"}
    flat = json.dumps(payload, ensure_ascii=False)
    for forbidden in [*PRICES, "price", "stock", "Demo Resident", "CARD-", "total", "NT$"]:
        assert forbidden not in flat, forbidden
    assert "untrusted" in system and "Never state" in system and system == SYSTEM_PROMPT


# ------------------------------------------------------------------ anthropic over a fake transport
def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def provider(handler, **kw) -> AnthropicProvider:
    return AnthropicProvider("sk-test-key", "test-model", 5, client_for(handler), **kw)


def ok(text="你好"):
    return lambda req: httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def test_request_shape_headers_and_body(facts):
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(url=str(req.url), method=req.method, headers=dict(req.headers), body=json.loads(req.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "回答"}]})

    out = provider(handler).generate(LLMRequest(*build_prompt(facts), facts))
    assert out == "回答"
    assert seen["url"] == ANTHROPIC_URL and seen["method"] == "POST"
    assert seen["headers"]["x-api-key"] == "sk-test-key"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    b = seen["body"]
    assert b["model"] == "test-model" and b["max_tokens"] > 0 and b["system"] == SYSTEM_PROMPT
    assert [m["role"] for m in b["messages"]] == ["user"]
    assert "sk-test-key" not in json.dumps(b)                       # key only in the header


def test_joins_text_blocks_and_ignores_others():
    h = lambda r: httpx.Response(200, json={"content": [
        {"type": "thinking", "thinking": "x"}, {"type": "text", "text": "甲"}, {"type": "text", "text": "乙"}]})
    assert provider(h).generate(LLMRequest("s", "u", None)) == "甲乙"


@pytest.mark.parametrize("status", [400, 401, 429, 500, 529])
def test_http_errors_become_provider_errors_without_body_or_key(status):
    h = lambda r: httpx.Response(status, json={"error": {"message": "sk-test-key leaked here"}})
    with pytest.raises(ProviderError) as e:
        provider(h).generate(LLMRequest("s", "u", None))
    assert str(e.value) == f"HTTP {status}" and "sk-test-key" not in str(e.value)


@pytest.mark.parametrize("exc,msg", [
    (httpx.ReadTimeout("t"), "request timed out"), (httpx.ConnectTimeout("t"), "request timed out"),
    (httpx.ConnectError("c"), "network error"),
])
def test_network_failures(exc, msg):
    def h(r): raise exc
    with pytest.raises(ProviderError, match=msg):
        provider(h).generate(LLMRequest("s", "u", None))


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="not json"),
    httpx.Response(200, json={"nope": 1}),
    httpx.Response(200, json={"content": "str"}),
    httpx.Response(200, json={"content": []}),
    httpx.Response(200, json={"content": [{"type": "text", "text": "   "}]}),
])
def test_malformed_or_empty_responses(response):
    with pytest.raises(ProviderError):
        provider(lambda r: response).generate(LLMRequest("s", "u", None))
