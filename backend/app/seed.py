"""Seed demo data: residents, health profiles, products, devices.

Run:  python -m app.seed
Idempotent: rows that already exist (matched by card_id / product_code /
device_code) are left untouched, so re-running never resets stock or sequence
state. All values are fictional demo data; nutrition numbers are rounded
approximations for teaching, not authoritative nutrition facts.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.models import Device, HealthProfile, Product, Resident

RESIDENTS = [
    {"card_id": "CARD-1001", "display_name": "Demo Resident",
     "dietary_preferences": ["low_sodium"], "allergies": []},
    {"card_id": "CARD-1002", "display_name": "Demo Resident 2",
     "dietary_preferences": ["vegetarian"], "allergies": ["peanut"]},
]


def _nutrition(summary: str, kcal: int, sodium: int, fiber: float, vit_c: float, potassium: int):
    return {
        "summary": summary,
        "per_100g": {
            "calories_kcal": kcal,
            "sodium_mg": sodium,
            "fiber_g": fiber,
            "vitamin_c_mg": vit_c,
            "potassium_mg": potassium,
        },
    }


# (product_code, name, category, price_per_kg (TWD), stock_grams, nutrition)
PRODUCTS = [
    (101, "番茄", "vegetable", "60.00", 20000,
     _nutrition("低熱量、鈉含量低，含維生素 C 與茄紅素。", 18, 5, 1.2, 14, 237)),
    (102, "青花菜", "vegetable", "90.00", 15000,
     _nutrition("維生素 C 與膳食纖維豐富，鈉含量低。", 34, 33, 2.6, 89, 316)),
    (103, "菠菜", "vegetable", "80.00", 12000,
     _nutrition("深綠色葉菜，含鉀、葉酸與鐵。", 23, 79, 2.2, 28, 558)),
    (104, "紅蘿蔔", "vegetable", "45.00", 25000,
     _nutrition("含 β-胡蘿蔔素與膳食纖維，熱量低。", 41, 69, 2.8, 6, 320)),
    (105, "地瓜", "root", "55.00", 30000,
     _nutrition("根莖類主食替代選項，膳食纖維與鉀含量高。", 86, 55, 3.0, 2.4, 337)),
    (106, "高麗菜", "vegetable", "35.00", 18000,
     _nutrition("熱量低、鈉含量低，含維生素 C 與纖維。", 25, 18, 2.5, 36, 170)),
    (107, "香蕉", "fruit", "70.00", 16000,
     _nutrition("含鉀，鈉含量極低，熱量較蔬菜高。", 89, 1, 2.6, 8.7, 358)),
    (108, "蘋果", "fruit", "120.00", 14000,
     _nutrition("含膳食纖維，鈉含量極低。", 52, 1, 2.4, 4.6, 107)),
]

DEVICES = [
    {"device_code": "DEV-001", "description": "Simulated smart scale #1 (software simulator)"},
]


def seed(db: Session) -> dict[str, int]:
    """Insert missing demo rows. Returns how many rows of each kind were created."""
    created = {"residents": 0, "products": 0, "devices": 0}

    for r in RESIDENTS:
        if db.scalar(select(Resident).where(Resident.card_id == r["card_id"])):
            continue
        db.add(Resident(
            card_id=r["card_id"],
            display_name=r["display_name"],
            health_profile=HealthProfile(
                dietary_preferences=r["dietary_preferences"], allergies=r["allergies"]
            ),
        ))
        created["residents"] += 1

    for code, name, category, price, stock, nutrition in PRODUCTS:
        if db.scalar(select(Product).where(Product.product_code == code)):
            continue
        db.add(Product(
            product_code=code, name=name, category=category,
            price_per_kg=Decimal(price), stock_grams=stock,
            min_weight_grams=50, max_weight_grams=5000,
            nutrition_json=nutrition, is_active=True,
        ))
        created["products"] += 1

    for d in DEVICES:
        if db.scalar(select(Device).where(Device.device_code == d["device_code"])):
            continue
        db.add(Device(device_code=d["device_code"], description=d["description"],
                      last_sequence_number=-1))
        created["devices"] += 1

    db.commit()
    return created


def main() -> None:
    with get_session_factory()() as db:
        created = seed(db)
    print("Seed complete. Newly created rows:", created)


if __name__ == "__main__":
    main()
