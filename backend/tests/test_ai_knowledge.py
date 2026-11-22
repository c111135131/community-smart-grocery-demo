import json
import re

import pytest

from app.ai.knowledge import get_knowledge_base, load_knowledge_base
from app.seed import PRODUCTS


def test_knowledge_base_loads_with_enough_unique_entries():
    kb = get_knowledge_base()
    ids = [e.id for e in kb.entries]
    assert len(ids) >= 10 and len(ids) == len(set(ids))
    assert all(re.fullmatch(r"nutrition_seed_\d{3}", i) for i in ids)


def test_every_entry_is_complete():
    for e in get_knowledge_base().entries:
        assert e.title.strip() and len(e.text) > 15 and e.keywords, e.id


def test_product_codes_reference_seeded_products_and_each_product_has_an_entry():
    seeded = {code for code, *_ in PRODUCTS}
    kb = get_knowledge_base()
    referenced = {c for e in kb.entries for c in e.product_codes}
    assert referenced <= seeded
    product_entries = {c for e in kb.entries if "product" in e.tags for c in e.product_codes}
    assert product_entries == seeded


def test_knowledge_base_states_it_is_educational_and_not_reviewed():
    d = get_knowledge_base().disclaimer
    assert "未經營養師" in d and "不具醫療效力" in d


def test_duplicate_ids_rejected(tmp_path):
    e = {"id": "x", "title": "t", "text": "some text here"}
    f = tmp_path / "kb.json"
    f.write_text(json.dumps({"entries": [e, e]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_knowledge_base(f)


def test_malformed_files_rejected(tmp_path):
    f = tmp_path / "kb.json"
    f.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_knowledge_base(f)
    f.write_text(json.dumps({"entries": [{"id": "x"}]}), encoding="utf-8")  # missing fields
    with pytest.raises(ValueError):
        load_knowledge_base(f)
