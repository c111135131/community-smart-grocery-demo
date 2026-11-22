"""Deterministic product ranking. The "decision" lives here, not in an LLM prompt.

Given the resident's preferences and the nutrition numbers stored in the database,
this module decides which in-stock products to highlight and why. The LLM (or the
mock provider) only *phrases* the result; it cannot change which products are picked
and is never given prices or stock quantities.

All thresholds are DEMO values for illustration, not medical standards.
"""
import re
from collections.abc import Collection
from dataclasses import dataclass, field

from app.ai.tools import ProductFact

# Demo threshold: with a low_sodium preference, products above this sodium level are
# left out whenever the question is not itself about sodium.
LOW_SODIUM_MAX_MG_PER_100G = 60
MAX_PICKS = 3
MAX_MENTIONED = 3

# Nutrients people often ask about but that the product data does NOT contain.
UNTRACKED_NUTRIENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("鐵", re.compile(r"鐵|貧血|\biron\b", re.I)),
    ("蛋白質", re.compile(r"蛋白質|protein", re.I)),
    ("維生素 B12", re.compile(r"b\s*12|維生素\s*b\s*12", re.I)),
    ("鈣", re.compile(r"鈣|calcium", re.I)),
    ("維生素 A", re.compile(r"維生素\s*a\b|維他命\s*a\b|vitamin\s*a\b", re.I)),
    ("葉酸", re.compile(r"葉酸|folate", re.I)),
)

PREFERENCE_LABELS = {"low_sodium": "低鈉", "vegetarian": "素食"}
ALLERGY_LABELS = {"peanut": "花生"}


@dataclass(frozen=True)
class Focus:
    key: str
    label: str
    metric: str  # key inside nutrition["per_100g"]
    unit: str
    higher_is_better: bool
    knowledge_tag: str
    pattern: re.Pattern[str]


FOCI: tuple[Focus, ...] = (
    Focus("sodium", "鈉", "sodium_mg", "毫克", False, "low_sodium",
          re.compile(r"低鈉|鈉|鹽|sodium", re.I)),
    Focus("vitamin_c", "維生素 C", "vitamin_c_mg", "毫克", True, "vitamin_c",
          re.compile(r"維生素\s*c|維他命\s*c|vitamin\s*c|抗氧化|免疫", re.I)),
    Focus("potassium", "鉀", "potassium_mg", "毫克", True, "potassium",
          re.compile(r"鉀|potassium", re.I)),
    Focus("fiber", "膳食纖維", "fiber_g", "公克", True, "fiber",
          re.compile(r"纖維|便秘|腸道|飽足|fiber|fibre", re.I)),
    Focus("calories", "熱量", "calories_kcal", "大卡", False, "low_calorie",
          re.compile(r"熱量|減重|減肥|低卡|卡路里|體重|calorie", re.I)),
)
_FOCUS_BY_KEY = {f.key: f for f in FOCI}
DEFAULT_FOCUS = _FOCUS_BY_KEY["fiber"]
# Which focus a stored preference implies when the question itself names none.
PREFERENCE_FOCUS = {"low_sodium": "sodium", "vegetarian": "fiber"}


@dataclass(frozen=True)
class Pick:
    product_code: int
    name: str
    category: str
    per_100g: dict[str, float]
    reasons: list[str]


@dataclass(frozen=True)
class Mentioned:
    product_code: int
    name: str
    in_stock: bool
    per_100g: dict[str, float]
    fit_note: str


@dataclass
class Recommendation:
    focus: Focus
    picks: list[Pick] = field(default_factory=list)
    mentioned: list[Mentioned] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _num(v: float) -> str:
    return f"{v:g}"


def _per_100g(p: ProductFact) -> dict[str, float]:
    raw = p.nutrition.get("per_100g") or {}
    return {k: v for k, v in raw.items() if isinstance(v, (int, float))}


def choose_focus(question: str, preferences: list[str]) -> Focus:
    """Focus named earliest in the question; else implied by a preference; else fiber."""
    best: tuple[int, int, Focus] | None = None
    for order, focus in enumerate(FOCI):
        m = focus.pattern.search(question)
        if m and (best is None or (m.start(), order) < best[:2]):
            best = (m.start(), order, focus)
    if best:
        return best[2]
    for pref in preferences:
        key = PREFERENCE_FOCUS.get(pref)
        if key:
            return _FOCUS_BY_KEY[key]
    return DEFAULT_FOCUS


def _fit_note(values: dict[str, float], preferences: list[str]) -> str:
    sodium = values.get("sodium_mg")
    if "low_sodium" in preferences and sodium is not None:
        if sodium <= LOW_SODIUM_MAX_MG_PER_100G:
            return f"每 100 公克鈉 {_num(sodium)} 毫克，符合您的低鈉偏好"
        return f"每 100 公克鈉 {_num(sodium)} 毫克，相對較高，低鈉偏好者可酌量食用"
    parts = [
        f"{label} {_num(values[key])} {unit}"
        for key, label, unit in (
            ("calories_kcal", "熱量", "大卡"), ("sodium_mg", "鈉", "毫克"),
            ("fiber_g", "膳食纖維", "公克"), ("vitamin_c_mg", "維生素 C", "毫克"),
        )
        if key in values
    ]
    return "每 100 公克：" + "、".join(parts) if parts else "目前沒有營養數值"


def recommend(
    question: str,
    preferences: list[str],
    inventory: list[ProductFact],
    mentioned_facts: list[ProductFact],
    *,
    excluded_product_codes: Collection[int] = (),
) -> Recommendation:
    """Rank in-stock products. `inventory` must include out-of-stock items so that a
    product named in the question can be reported as sold out instead of ignored."""
    focus = choose_focus(question, preferences)
    rec = Recommendation(focus=focus)
    for label, pattern in UNTRACKED_NUTRIENTS:
        if pattern.search(question):
            rec.notes.append(
                f"本店商品的營養資料目前沒有「{label}」的數值，無法依{label}替商品排序；"
                f"以下商品改以「{focus.label}」排序，{label}相關資訊請參考下方知識。"
            )

    candidates = [
        p for p in inventory
        if p.in_stock and p.product_code not in excluded_product_codes and focus.metric in _per_100g(p)
    ]
    if "low_sodium" in preferences and focus.key != "sodium":
        kept = [
            p for p in candidates
            if _per_100g(p).get("sodium_mg", 0) <= LOW_SODIUM_MAX_MG_PER_100G
        ]
        if len(kept) < len(candidates):
            rec.notes.append(
                f"已依您的低鈉偏好排除鈉含量較高的商品（示範門檻：每 100 公克超過 "
                f"{LOW_SODIUM_MAX_MG_PER_100G} 毫克）。"
            )
        candidates = kept

    candidates.sort(
        key=lambda p: (
            -_per_100g(p)[focus.metric] if focus.higher_is_better else _per_100g(p)[focus.metric],
            p.product_code,
        )
    )
    for p in candidates[:MAX_PICKS]:
        v = _per_100g(p)
        reasons = [f"{focus.label}：每 100 公克 {_num(v[focus.metric])} {focus.unit}"]
        if "low_sodium" in preferences and focus.key != "sodium" and "sodium_mg" in v:
            reasons.append(f"鈉：每 100 公克 {_num(v['sodium_mg'])} 毫克（符合低鈉偏好）")
        rec.picks.append(Pick(p.product_code, p.name, p.category, v, reasons))

    in_stock_by_code = {p.product_code: p.in_stock for p in inventory}
    for p in mentioned_facts[:MAX_MENTIONED]:
        v = _per_100g(p)
        rec.mentioned.append(
            Mentioned(p.product_code, p.name, in_stock_by_code.get(p.product_code, p.in_stock),
                      v, _fit_note(v, preferences))
        )
    return rec


def mentioned_products(question: str, inventory: list[ProductFact]) -> list[ProductFact]:
    """Products whose name appears in the question (longest names first, no duplicates)."""
    found = [p for p in inventory if p.name and p.name in question]
    return sorted(found, key=lambda p: (-len(p.name), p.product_code))[:MAX_MENTIONED]
