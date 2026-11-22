"""Resident request/response schemas."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    card_id: str = Field(min_length=1, max_length=32, examples=["CARD-1001"])

    @field_validator("card_id")
    @classmethod
    def strip_and_require(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("card_id must not be blank")
        return v


class HealthProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dietary_preferences: list[str]
    allergies: list[str]
    notes: str | None = None


class ResidentOut(BaseModel):
    """Returned by login and GET /residents/{id}."""

    resident_id: int
    display_name: str
    health_profile: HealthProfileOut
