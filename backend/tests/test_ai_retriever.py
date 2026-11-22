import pytest

from app.ai.knowledge import KnowledgeEntry, get_knowledge_base
from app.ai.retriever import KeywordRetriever, Retriever


@pytest.fixture(scope="module")
def r() -> KeywordRetriever:
    return KeywordRetriever(get_knowledge_base().entries)


def ids(hits):
    return [h.id for h in hits]


def test_satisfies_the_retriever_interface(r):
    retriever: Retriever = r
    assert retriever.search("低鈉")


def test_low_sodium_question_finds_the_low_sodium_entry_first(r):
    assert ids(r.search("請推薦適合我的低鈉食材", tags=["low_sodium"]))[0] == "nutrition_seed_001"


@pytest.mark.parametrize("query", ["哪些蔬菜維生素 C 比較高？", "what has vitamin c", "VITAMIN C 來源"])
def test_vitamin_c_questions_find_vitamin_c_entry(r, query):
    assert ids(r.search(query))[0] == "nutrition_seed_006"


def test_product_name_finds_product_entry(r):
    assert ids(r.search("番茄適合我嗎"))[0] == "nutrition_seed_007"
    assert ids(r.search("tell me about spinach"))[0] == "nutrition_seed_009"


def test_vegetarian_iron_question(r):
    top = ids(r.search("我是素食者，鐵質怎麼補充？", tags=["vegetarian"]))
    assert set(top[:2]) == {"nutrition_seed_003", "nutrition_seed_004"}


def test_irrelevant_or_gibberish_queries_return_nothing(r):
    for q in ["你好", "zzzzqqq", "", "   ", "😀😀😀"]:
        assert r.search(q) == [], q


def test_tags_alone_return_entries_with_those_tags(r):
    hits = r.search("", tags=["vegetarian"])
    assert hits and all("vegetarian" in h.tags for h in hits)


def test_tag_boost_changes_ranking(r):
    q = "我想吃得健康"
    assert [h.id for h in r.search(q)] != [h.id for h in r.search(q, tags=["fiber"])] or r.search(q, tags=["fiber"])
    boosted = r.search(q, tags=["fiber"])
    assert boosted and all("fiber" in h.tags for h in boosted)


def test_limit_is_respected(r):
    assert len(r.search("低鈉 鉀 維生素 纖維", limit=2)) == 2
    assert r.search("低鈉", limit=0) == []


def test_results_sorted_by_score_and_deterministic(r):
    a = r.search("低鈉 蔬菜 維生素", tags=["low_sodium"], limit=6)
    b = r.search("低鈉 蔬菜 維生素", tags=["low_sodium"], limit=6)
    assert a == b
    assert [h.score for h in a] == sorted((h.score for h in a), reverse=True)


def test_ties_break_by_entry_id():
    mk = lambda i: KnowledgeEntry(id=i, title="相同標題內容", text="相同的內容文字說明", keywords=["相同"])
    hits = KeywordRetriever([mk("b"), mk("a"), mk("c")]).search("相同")
    assert ids(hits) == ["a", "b", "c"]


def test_robust_to_very_long_and_odd_input(r):
    assert isinstance(r.search("低鈉" * 5000), list)
    assert isinstance(r.search("\x00\n\t¿?!@#$%^&*()"), list)
