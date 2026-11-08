from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ngo_profile: Mapped["NGOProfile | None"] = relationship(back_populates="user", uselist=False)
    volunteer_profile: Mapped["VolunteerProfile | None"] = relationship(back_populates="user", uselist=False)


class NGOProfile(Base):
    __tablename__ = "ngo_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    organization_name: Mapped[str] = mapped_column(String(180))
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    service_area: Mapped[str] = mapped_column(String(180), default="")
    accepted_categories: Mapped[str] = mapped_column(String(500), default="all")
    receiving_capacity: Mapped[int] = mapped_column(Integer, default=100)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="ngo_profile")


class VolunteerProfile(Base):
    __tablename__ = "volunteer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), default="")
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    service_area: Mapped[str] = mapped_column(String(180), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="volunteer_profile")


class Donation(Base):
    __tablename__ = "donations"

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ngo_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(60), index=True)
    quantity_servings: Mapped[int] = mapped_column(Integer)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pickup_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    storage_method: Mapped[str] = mapped_column(String(120))
    storage_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    allergens: Mapped[str] = mapped_column(String(300), default="Not specified")
    packaging_condition: Mapped[str] = mapped_column(String(120))
    pickup_address: Mapped[str] = mapped_column(String(300))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="awaiting_match", index=True)
    safety_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DonationMatch(Base):
    __tablename__ = "donation_matches"
    __table_args__ = (UniqueConstraint("donation_id", "ngo_id", name="uq_match_donation_ngo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donations.id"), index=True)
    ngo_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donations.id"), unique=True, index=True)
    ngo_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    volunteer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="accepted", index=True)
    proof_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeliveryStatusHistory(Base):
    __tablename__ = "delivery_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VolunteerAssignment(Base):
    __tablename__ = "delivery_assignments"
    __table_args__ = (UniqueConstraint("delivery_id", "volunteer_id", name="uq_delivery_volunteer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), index=True)
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="assigned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SafetyReport(Base):
    __tablename__ = "food_safety_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donations.id"), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
