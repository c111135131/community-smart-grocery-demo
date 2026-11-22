"""Resident business logic (kept out of route handlers and React components)."""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Resident
from app.schemas.resident import HealthProfileOut, ResidentOut


class UnknownCardError(Exception):
    """The card ID is not registered."""


class ResidentNotFoundError(Exception):
    """No resident with the given ID."""


def _to_out(resident: Resident) -> ResidentOut:
    profile = resident.health_profile
    return ResidentOut(
        resident_id=resident.id,
        display_name=resident.display_name,
        health_profile=HealthProfileOut(
            dietary_preferences=list(profile.dietary_preferences) if profile else [],
            allergies=list(profile.allergies) if profile else [],
            notes=profile.notes if profile else None,
        ),
    )


def login_with_card(db: Session, card_id: str) -> ResidentOut:
    """Demo login: look up a seeded card ID.

    NOT production authentication: there is no secret, session, or token. It only
    simulates tapping an NFC/RFID resident card (see CLAUDE.md scope boundaries).
    """
    resident = db.scalar(
        select(Resident)
        .options(joinedload(Resident.health_profile))
        .where(Resident.card_id == card_id)
    )
    if resident is None:
        raise UnknownCardError(card_id)
    return _to_out(resident)


def get_resident(db: Session, resident_id: int) -> ResidentOut:
    resident = db.scalar(
        select(Resident)
        .options(joinedload(Resident.health_profile))
        .where(Resident.id == resident_id)
    )
    if resident is None:
        raise ResidentNotFoundError(resident_id)
    return _to_out(resident)
