import inspect

import pytest

from app.ai.retriever import KeywordRetriever
from app.ai.knowledge import get_knowledge_base
from app.ai.tools import TOOL_DESCRIPTIONS, TOOL_NAMES, ToolBox, ToolRunner
from app.models import Cart, CartItem, Device, IotEvent, Order, Product


@pytest.fixture()
def box(db_session):
    return ToolBox(db_session, KeywordRetriever(get_knowledge_base().entries))


def test_exactly_three_read_only_tools_exist():
    assert TOOL_NAMES == ("get_product_info", "get_inventory", "search_nutrition_knowledge")
    public = {n for n, _ in inspect.getmembers(ToolBox, inspect.isfunction) if not n.startswith("_")}
    assert public == set(TOOL_NAMES)            # nothing else can be called, no write methods
    assert all(TOOL_DESCRIPTIONS[n] for n in TOOL_NAMES)
    assert all("Read-only" in TOOL_DESCRIPTIONS[n] for n in TOOL_NAMES)


def test_get_product_info(box):
    p = box.get_product_info(101)
    assert (p.name, p.in_stock, p.stock_grams) == ("番茄", True, 20000)
    assert p.model_dump(mode="json")["price_per_kg"] == "60.00"   # as stored, a string
    assert p.nutrition["per_100g"]["sodium_mg"] == 5


@pytest.mark.parametrize("code", [999, 0, -1, 70000])
def test_get_product_info_unknown_or_out_of_range(box, code):
    assert box.get_product_info(code) is None


def test_inactive_product_not_visible(box, db_session):
    db_session.query(Product).filter_by(product_code=101).one().is_active = False
    db_session.commit()
    assert box.get_product_info(101) is None
    assert 101 not in [p.product_code for p in box.get_inventory(in_stock_only=False)]


def test_get_inventory_filters(box, db_session):
    assert len(box.get_inventory()) == 8
    db_session.query(Product).filter_by(product_code=107).one().stock_grams = 0
    db_session.commit()
    assert 107 not in [p.product_code for p in box.get_inventory(in_stock_only=True)]
    out = {p.product_code: p.in_stock for p in box.get_inventory(in_stock_only=False)}
    assert out[107] is False and out[108] is True
    assert [p.product_code for p in box.get_inventory(False, "fruit")] == [107, 108]
    assert box.get_inventory(category="nope") == []


def test_search_tool_clamps_limit_and_truncates_query(box):
    assert len(box.search_nutrition_knowledge("低鈉 鉀 維生素 纖維", limit=100)) <= 10
    assert len(box.search_nutrition_knowledge("低鈉 鉀 維生素 纖維", limit=0)) == 1
    assert isinstance(box.search_nutrition_knowledge("低鈉" * 10000), list)
    hits = box.search_nutrition_knowledge("低鈉", tags=["low_sodium"])
    assert hits[0].id == "nutrition_seed_001" and hits[0].model_dump()["score"] > 0


def _snapshot(db):
    db.expire_all()
    return (
        [(p.product_code, p.stock_grams, str(p.price_per_kg), p.is_active) for p in db.query(Product).order_by(Product.id)],
        db.query(Order).count(), db.query(Cart).count(), db.query(CartItem).count(),
        db.query(IotEvent).count(), [d.last_sequence_number for d in db.query(Device)],
    )


def test_tools_never_modify_the_database(box, db_session):
    before = _snapshot(db_session)
    box.get_product_info(101); box.get_inventory(); box.get_inventory(False, "fruit")
    box.search_nutrition_knowledge("低鈉", tags=["low_sodium"])
    assert not (db_session.new or db_session.dirty or db_session.deleted)
    assert _snapshot(db_session) == before


def test_runner_records_traces_and_rejects_unknown_tools(box):
    run = ToolRunner(box)
    run.call("get_inventory", in_stock_only=False)
    run.call("get_product_info", product_code=999)
    run.call("search_nutrition_knowledge", query="低鈉 鉀", limit=2)
    assert [(t.name, t.result_count) for t in run.traces] == [
        ("get_inventory", 8), ("get_product_info", 0), ("search_nutrition_knowledge", 2)]
    for bad in ["update_stock", "checkout", "set_price", "__init__", "get_resident"]:
        with pytest.raises(ValueError):
            run.call(bad)
    assert len(run.traces) == 3
