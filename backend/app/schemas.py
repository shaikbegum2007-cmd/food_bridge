from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


Role = Literal["donor", "ngo", "volunteer"]
Category = Literal["prepared meals", "produce", "bakery", "dairy", "packaged"]


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: Role
    organization_name: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=30)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class DonationInput(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    category: Category
    quantity_servings: int = Field(gt=0, le=100_000)
    prepared_at: datetime
    pickup_deadline: datetime
    storage_method: str = Field(min_length=2, max_length=120)
    storage_temperature_c: float | None = Field(default=None, ge=-80, le=100)
    allergens: str = Field(default="Not specified", max_length=300)
    packaging_condition: str = Field(min_length=2, max_length=120)
    pickup_address: str = Field(min_length=5, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    photo_url: str | None = Field(default=None, max_length=500)

    @field_validator("prepared_at", "pickup_deadline")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("A timezone is required.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_times(self):
        now = datetime.now(timezone.utc)
        if self.prepared_at > now:
            raise ValueError("Preparation time cannot be in the future.")
        if self.pickup_deadline <= now:
            raise ValueError("Pickup deadline must be in the future.")
        if self.pickup_deadline <= self.prepared_at:
            raise ValueError("Pickup deadline must be after preparation.")
        return self


class NGOProfileInput(BaseModel):
    service_area: str = Field(min_length=2, max_length=180)
    accepted_categories: list[Category] = Field(min_length=1)
    receiving_capacity: int = Field(gt=0, le=100_000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class VolunteerProfileInput(BaseModel):
    phone: str = Field(min_length=7, max_length=30)
    available: bool
    service_area: str = Field(min_length=2, max_length=180)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class AssignInput(BaseModel):
    volunteer_id: int = Field(gt=0)


class StatusInput(BaseModel):
    status: Literal["pickup_confirmed", "in_transit", "delivered", "failed_pickup"]
    proof_url: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=300)


class SafetyReportInput(BaseModel):
    description: str = Field(min_length=10, max_length=2000)


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
