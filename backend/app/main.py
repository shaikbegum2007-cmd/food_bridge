import asyncio
import math
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import SessionLocal, get_db
from .models import (
    Delivery,
    DeliveryStatusHistory,
    Donation,
    DonationMatch,
    NGOProfile,
    SafetyReport,
    User,
    VolunteerAssignment,
    VolunteerProfile,
)
from .schemas import (
    AssignInput,
    DonationInput,
    LoginInput,
    NGOProfileInput,
    RegisterInput,
    SafetyReportInput,
    StatusInput,
    VolunteerProfileInput,
)
from .security import create_token, get_current_user, hash_password, require_roles, verify_password


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def _expiry_worker():
    while True:
        await asyncio.sleep(60)
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            expired = db.query(Donation).filter(Donation.status == "awaiting_match").all()
            for donation in expired:
                if _utc(donation.pickup_deadline) <= now:
                    donation.status = "expired"
            db.commit()
        finally:
            db.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    task = asyncio.create_task(_expiry_worker())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="FoodBridge API", version="0.1.0", lifespan=lifespan)
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _user_json(user: User) -> dict:
    result = {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
    if user.role == "ngo" and user.ngo_profile:
        profile = user.ngo_profile
        result["ngo_profile"] = {
            "organization_name": profile.organization_name,
            "verification_status": profile.verification_status,
            "service_area": profile.service_area,
            "accepted_categories": profile.accepted_categories.split(",") if profile.accepted_categories != "all" else ["all"],
            "receiving_capacity": profile.receiving_capacity,
            "latitude": profile.latitude,
            "longitude": profile.longitude,
        }
    if user.role == "volunteer" and user.volunteer_profile:
        profile = user.volunteer_profile
        result["volunteer_profile"] = {
            "phone": profile.phone,
            "verification_status": profile.verification_status,
            "available": profile.available,
            "service_area": profile.service_area,
            "latitude": profile.latitude,
            "longitude": profile.longitude,
        }
    return result


def _donation_json(donation: Donation, db: Session) -> dict:
    donor = db.get(User, donation.donor_id)
    ngo = db.get(User, donation.ngo_id) if donation.ngo_id else None
    return {
        "id": donation.id,
        "title": donation.title,
        "category": donation.category,
        "quantity_servings": donation.quantity_servings,
        "prepared_at": _utc(donation.prepared_at).isoformat(),
        "pickup_deadline": _utc(donation.pickup_deadline).isoformat(),
        "storage_method": donation.storage_method,
        "storage_temperature_c": donation.storage_temperature_c,
        "allergens": donation.allergens,
        "packaging_condition": donation.packaging_condition,
        "pickup_address": donation.pickup_address,
        "latitude": donation.latitude,
        "longitude": donation.longitude,
        "photo_url": donation.photo_url,
        "status": donation.status,
        "safety_note": donation.safety_note,
        "donor_id": donation.donor_id,
        "donor_name": donor.name if donor else "Unknown",
        "ngo_id": donation.ngo_id,
        "ngo_name": ngo.name if ngo else None,
        "created_at": _utc(donation.created_at).isoformat(),
    }


def _delivery_json(delivery: Delivery, db: Session) -> dict:
    donation = db.get(Donation, delivery.donation_id)
    ngo = db.get(User, delivery.ngo_id)
    ngo_profile = db.query(NGOProfile).filter_by(user_id=delivery.ngo_id).first()
    volunteer = db.get(User, delivery.volunteer_id) if delivery.volunteer_id else None
    history = (
        db.query(DeliveryStatusHistory)
        .filter(DeliveryStatusHistory.delivery_id == delivery.id)
        .order_by(DeliveryStatusHistory.created_at, DeliveryStatusHistory.id)
        .all()
    )
    return {
        "id": delivery.id,
        "status": delivery.status,
        "donation": _donation_json(donation, db) if donation else None,
        "ngo_id": delivery.ngo_id,
        "ngo_name": ngo.name if ngo else "Unknown",
        "destination_address": ngo_profile.service_area if ngo_profile and ngo_profile.service_area else (ngo.name if ngo else "Receiving organization"),
        "destination_latitude": ngo_profile.latitude if ngo_profile else None,
        "destination_longitude": ngo_profile.longitude if ngo_profile else None,
        "volunteer_id": delivery.volunteer_id,
        "volunteer_name": volunteer.name if volunteer else None,
        "proof_url": delivery.proof_url,
        "history": [
            {"status": event.status, "note": event.note, "created_at": _utc(event.created_at).isoformat()}
            for event in history
        ],
    }


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    delta_p = math.radians(lat2 - lat1)
    delta_l = math.radians(lon2 - lon1)
    a = math.sin(delta_p / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(delta_l / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _weights() -> dict[str, float]:
    values = {
        "distance": float(os.getenv("MATCH_WEIGHT_DISTANCE", "30")),
        "urgency": float(os.getenv("MATCH_WEIGHT_URGENCY", "25")),
        "quantity": float(os.getenv("MATCH_WEIGHT_QUANTITY", "20")),
        "category": float(os.getenv("MATCH_WEIGHT_CATEGORY", "15")),
        "volunteer": float(os.getenv("MATCH_WEIGHT_VOLUNTEER", "10")),
    }
    if any(value < 0 for value in values.values()) or sum(values.values()) <= 0:
        raise RuntimeError("Matching weights must be non-negative and have a positive sum.")
    total = sum(values.values())
    return {key: value / total for key, value in values.items()}


def _expire_stale_donations(db: Session) -> None:
    now = datetime.now(timezone.utc)
    stale = db.query(Donation).filter(Donation.status == "awaiting_match").all()
    changed = False
    for donation in stale:
        if _utc(donation.pickup_deadline) <= now:
            donation.status = "expired"
            changed = True
    if changed:
        db.commit()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", status_code=201)
def register(body: RegisterInput, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    if body.role == "ngo":
        db.add(
            NGOProfile(
                user_id=user.id,
                organization_name=(body.organization_name or body.name).strip(),
                verification_status="pending",
            )
        )
    elif body.role == "volunteer":
        db.add(VolunteerProfile(user_id=user.id, phone=(body.phone or "").strip()))
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user), "token_type": "bearer", "user": _user_json(user)}


@app.post("/auth/login")
def login(body: LoginInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is suspended.")
    return {"access_token": create_token(user), "token_type": "bearer", "user": _user_json(user)}


@app.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return _user_json(user)


@app.put("/ngo/profile")
def update_ngo_profile(
    body: NGOProfileInput,
    user: User = Depends(require_roles("ngo")),
    db: Session = Depends(get_db),
):
    profile = db.query(NGOProfile).filter_by(user_id=user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Organization profile not found.")
    profile.service_area = body.service_area
    profile.accepted_categories = ",".join(body.accepted_categories)
    profile.receiving_capacity = body.receiving_capacity
    profile.latitude = body.latitude
    profile.longitude = body.longitude
    db.commit()
    db.refresh(user)
    return _user_json(user)


@app.put("/volunteer/profile")
def update_volunteer_profile(
    body: VolunteerProfileInput,
    user: User = Depends(require_roles("volunteer")),
    db: Session = Depends(get_db),
):
    profile = db.query(VolunteerProfile).filter_by(user_id=user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Volunteer profile not found.")
    profile.phone = body.phone.strip()
    profile.available = body.available
    profile.service_area = body.service_area
    profile.latitude = body.latitude
    profile.longitude = body.longitude
    db.commit()
    return {
        "phone": profile.phone,
        "verification_status": profile.verification_status,
        "available": profile.available,
        "service_area": profile.service_area,
    }


@app.get("/admin/volunteers")
def list_volunteer_applications(
    user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)
):
    profiles = db.query(VolunteerProfile).order_by(VolunteerProfile.id.desc()).limit(500).all()
    return [
        {
            "user_id": profile.user_id,
            "name": profile.user.name,
            "email": profile.user.email,
            "phone": profile.phone,
            "service_area": profile.service_area,
            "verification_status": profile.verification_status,
        }
        for profile in profiles
    ]


@app.post("/admin/volunteers/{volunteer_id}/review")
def review_volunteer(
    volunteer_id: int,
    decision: str,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Decision must be approved or rejected.")
    profile = db.query(VolunteerProfile).filter_by(user_id=volunteer_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Volunteer application not found.")
    if decision == "approved" and len("".join(character for character in profile.phone if character.isdigit())) < 7:
        raise HTTPException(status_code=409, detail="The volunteer must provide a valid phone number before approval.")
    profile.verification_status = decision
    db.commit()
    return {"user_id": volunteer_id, "verification_status": profile.verification_status}


@app.get("/admin/ngos")
def list_ngo_applications(
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    profiles = db.query(NGOProfile).order_by(NGOProfile.id.desc()).all()
    return [
        {
            "user_id": profile.user_id,
            "name": profile.organization_name,
            "email": profile.user.email,
            "verification_status": profile.verification_status,
            "service_area": profile.service_area,
        }
        for profile in profiles
    ]


@app.post("/admin/ngos/{ngo_id}/review")
def review_ngo(
    ngo_id: int,
    decision: str,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Decision must be approved or rejected.")
    profile = db.query(NGOProfile).filter_by(user_id=ngo_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="NGO application not found.")
    profile.verification_status = decision
    db.commit()
    return {"user_id": ngo_id, "verification_status": profile.verification_status}


@app.post("/donations", status_code=201)
def create_donation(
    body: DonationInput,
    user: User = Depends(require_roles("donor")),
    db: Session = Depends(get_db),
):
    donation = Donation(donor_id=user.id, **body.model_dump())
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return _donation_json(donation, db)


@app.get("/donations")
def list_donations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _expire_stale_donations(db)
    query = db.query(Donation)
    if user.role == "donor":
        query = query.filter(Donation.donor_id == user.id)
    elif user.role == "ngo":
        query = query.filter((Donation.status == "awaiting_match") | (Donation.ngo_id == user.id))
    elif user.role == "volunteer":
        assigned_ids = db.query(Delivery.donation_id).filter(Delivery.volunteer_id == user.id)
        query = query.filter((Donation.status == "awaiting_match") | (Donation.id.in_(assigned_ids)))
    donations = query.order_by(Donation.created_at.desc()).limit(200).all()
    return [_donation_json(item, db) for item in donations]


@app.get("/donations/{donation_id}/matches")
def get_matches(
    donation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _expire_stale_donations(db)
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found.")
    if user.role != "admin" and donation.donor_id != user.id:
        raise HTTPException(status_code=403, detail="Only the donating organization can view match recommendations.")
    if donation.status != "awaiting_match" or _utc(donation.pickup_deadline) <= datetime.now(timezone.utc):
        return []
    now = datetime.now(timezone.utc)
    profiles = (
        db.query(NGOProfile)
        .filter(NGOProfile.verification_status == "approved")
        .order_by(NGOProfile.user_id)
        .all()
    )
    weights = _weights()
    matches = []
    available_volunteers = (
        db.query(VolunteerProfile)
        .filter(VolunteerProfile.available.is_(True), VolunteerProfile.latitude.isnot(None))
        .all()
    )
    for profile in profiles:
        if profile.latitude is None or profile.longitude is None:
            continue
        categories = profile.accepted_categories.split(",")
        if "all" not in categories and donation.category not in categories:
            continue
        distance = _distance_km(donation.latitude, donation.longitude, profile.latitude, profile.longitude)
        if distance > 50:
            continue
        outstanding = (
            db.query(func.count(Delivery.id))
            .filter(Delivery.ngo_id == profile.user_id, Delivery.status.notin_(["completed", "failed_pickup"]))
            .scalar()
            or 0
        )
        if outstanding >= 3:
            continue
        distance_score = max(0.0, 100.0 * (1.0 - distance / 50.0))
        remaining_hours = max(0.0, (_utc(donation.pickup_deadline) - now).total_seconds() / 3600)
        urgency_score = max(0.0, 100.0 * (1.0 - min(remaining_hours / 24.0, 1.0)))
        quantity_score = min(donation.quantity_servings / profile.receiving_capacity, profile.receiving_capacity / donation.quantity_servings) * 100
        category_score = 100.0
        volunteer_available = any(
            volunteer.latitude is not None
            and volunteer.longitude is not None
            and _distance_km(donation.latitude, donation.longitude, volunteer.latitude, volunteer.longitude) <= 50
            and (
                db.query(func.count(Delivery.id))
                .filter(Delivery.volunteer_id == volunteer.user_id, Delivery.status.notin_(["completed", "failed_pickup"]))
                .scalar()
                or 0
            ) < 1
            for volunteer in available_volunteers
        )
        volunteer_score = 100.0 if volunteer_available else 0.0
        score = (
            distance_score * weights["distance"]
            + urgency_score * weights["urgency"]
            + quantity_score * weights["quantity"]
            + category_score * weights["category"]
            + volunteer_score * weights["volunteer"]
        )
        ngo = db.get(User, profile.user_id)
        explanation = (
            f"{distance:.1f} km away; accepts {donation.category}; "
            f"capacity {profile.receiving_capacity} servings; "
            f"{'a nearby volunteer is available' if volunteer_available else 'no nearby volunteer is currently available'}."
        )
        match = db.query(DonationMatch).filter_by(donation_id=donation.id, ngo_id=profile.user_id).first()
        if match is None:
            match = DonationMatch(donation_id=donation.id, ngo_id=profile.user_id, score=score, distance_km=distance, explanation=explanation)
            db.add(match)
        else:
            match.score, match.distance_km, match.explanation, match.created_at = score, distance, explanation, now
        matches.append({
            "ngo_id": profile.user_id,
            "organization_name": profile.organization_name,
            "score": round(score, 1),
            "distance_km": round(distance, 1),
            "receiving_capacity": profile.receiving_capacity,
            "verification_status": profile.verification_status,
            "volunteer_available": volunteer_available,
            "explanation": explanation,
        })
    db.commit()
    return sorted(matches, key=lambda match: (-match["score"], match["distance_km"]))


@app.post("/donations/{donation_id}/accept", status_code=201)
def accept_donation(
    donation_id: int,
    user: User = Depends(require_roles("ngo")),
    db: Session = Depends(get_db),
):
    _expire_stale_donations(db)
    profile = db.query(NGOProfile).filter_by(user_id=user.id).first()
    if profile is None or profile.verification_status != "approved":
        raise HTTPException(status_code=403, detail="Only verified NGOs can accept donations.")
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Donation)
        .where(
            Donation.id == donation_id,
            Donation.status == "awaiting_match",
            Donation.pickup_deadline > now,
            Donation.safety_note.is_(None),
        )
        .values(status="accepted", ngo_id=user.id)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This donation is no longer available or has expired.")
    delivery = Delivery(donation_id=donation_id, ngo_id=user.id, status="accepted")
    db.add(delivery)
    try:
        db.flush()
        db.add(DeliveryStatusHistory(delivery_id=delivery.id, actor_id=user.id, status="accepted", note="Donation accepted by verified NGO."))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This donation has already been accepted.")
    db.refresh(delivery)
    return _delivery_json(delivery, db)


@app.get("/deliveries")
def list_deliveries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Delivery)
    if user.role == "ngo":
        query = query.filter(Delivery.ngo_id == user.id)
    elif user.role == "volunteer":
        query = query.filter(Delivery.volunteer_id == user.id)
    elif user.role == "donor":
        donor_donation_ids = db.query(Donation.id).filter(Donation.donor_id == user.id)
        query = query.filter(Delivery.donation_id.in_(donor_donation_ids))
    return [_delivery_json(delivery, db) for delivery in query.order_by(Delivery.created_at.desc()).limit(200).all()]


@app.get("/volunteers/recommendations/{delivery_id}")
def volunteer_recommendations(
    delivery_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found.")
    if user.role not in {"admin", "ngo"} or (user.role == "ngo" and delivery.ngo_id != user.id):
        raise HTTPException(status_code=403, detail="Only the receiving NGO can view volunteer recommendations.")
    donation = db.get(Donation, delivery.donation_id)
    volunteers = (
        db.query(VolunteerProfile)
        .filter(VolunteerProfile.available.is_(True), VolunteerProfile.verification_status == "approved")
        .all()
    )
    candidates = []
    for profile in volunteers:
        if profile.latitude is None or profile.longitude is None:
            continue
        if delivery.status == "failed_pickup" and profile.user_id == delivery.volunteer_id:
            continue
        active = (
            db.query(func.count(Delivery.id))
            .filter(Delivery.volunteer_id == profile.user_id, Delivery.status.notin_(["completed", "failed_pickup"]))
            .scalar()
            or 0
        )
        distance = _distance_km(donation.latitude, donation.longitude, profile.latitude, profile.longitude)
        if active == 0 and distance <= 50:
            volunteer = db.get(User, profile.user_id)
            candidates.append({"volunteer_id": volunteer.id, "name": volunteer.name, "distance_km": round(distance, 1)})
    return sorted(candidates, key=lambda candidate: candidate["distance_km"])


@app.post("/deliveries/{delivery_id}/assign", status_code=201)
def assign_volunteer(
    delivery_id: int,
    body: AssignInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found.")
    if user.role not in {"admin", "ngo"} or (user.role == "ngo" and delivery.ngo_id != user.id):
        raise HTTPException(status_code=403, detail="Only the receiving NGO can assign this delivery.")
    if delivery.status not in {"accepted", "volunteer_assigned", "failed_pickup"}:
        raise HTTPException(status_code=409, detail="A volunteer cannot be assigned at this delivery stage.")
    volunteer = db.get(User, body.volunteer_id)
    profile = db.query(VolunteerProfile).filter_by(user_id=body.volunteer_id).first()
    if volunteer is None or volunteer.role != "volunteer" or profile is None or not profile.available or profile.verification_status != "approved":
        raise HTTPException(status_code=422, detail="Choose an active volunteer with an available profile.")
    active = (
        db.query(func.count(Delivery.id))
        .filter(Delivery.volunteer_id == volunteer.id, Delivery.status.notin_(["completed", "failed_pickup"]))
        .scalar()
        or 0
    )
    donation = db.get(Donation, delivery.donation_id)
    if profile.latitude is None or profile.longitude is None or _distance_km(donation.latitude, donation.longitude, profile.latitude, profile.longitude) > 50 or active:
        raise HTTPException(status_code=409, detail="This volunteer is unavailable or outside the pickup service radius.")
    assignment = db.query(VolunteerAssignment).filter_by(delivery_id=delivery.id, volunteer_id=volunteer.id).first()
    if assignment and assignment.status != "assigned":
        raise HTTPException(status_code=409, detail="A volunteer who already acted on this delivery cannot be assigned again.")
    delivery.volunteer_id = volunteer.id
    delivery.status = "volunteer_assigned"
    donation = db.get(Donation, delivery.donation_id)
    donation.status = "volunteer_assigned"
    if assignment is None:
        db.add(VolunteerAssignment(delivery_id=delivery.id, volunteer_id=volunteer.id))
    db.add(DeliveryStatusHistory(delivery_id=delivery.id, actor_id=user.id, status="volunteer_assigned"))
    db.commit()
    db.refresh(delivery)
    return _delivery_json(delivery, db)


@app.post("/deliveries/{delivery_id}/accept-task")
def accept_task(
    delivery_id: int,
    user: User = Depends(require_roles("volunteer")),
    db: Session = Depends(get_db),
):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None or delivery.volunteer_id != user.id or delivery.status != "volunteer_assigned":
        raise HTTPException(status_code=409, detail="This task is not assigned to you or is no longer available.")
    assignment = db.query(VolunteerAssignment).filter_by(delivery_id=delivery.id, volunteer_id=user.id).first()
    if assignment is None or assignment.status != "assigned":
        raise HTTPException(status_code=409, detail="This assignment has already been acted on.")
    assignment.status = "accepted"
    delivery.status = "volunteer_accepted"
    donation = db.get(Donation, delivery.donation_id)
    donation.status = "volunteer_accepted"
    db.add(DeliveryStatusHistory(delivery_id=delivery.id, actor_id=user.id, status="volunteer_accepted", note="Volunteer accepted the task."))
    db.commit()
    return _delivery_json(delivery, db)


@app.post("/deliveries/{delivery_id}/status")
def update_delivery_status(
    delivery_id: int,
    body: StatusInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found.")
    if user.role != "volunteer" or delivery.volunteer_id != user.id:
        raise HTTPException(status_code=403, detail="Only the assigned volunteer can update pickup and transit status.")
    transitions = {
        "volunteer_assigned": {"pickup_confirmed", "failed_pickup"},
        "volunteer_accepted": {"pickup_confirmed", "failed_pickup"},
        "pickup_confirmed": {"in_transit", "failed_pickup"},
        "in_transit": {"delivered", "failed_pickup"},
    }
    if body.status not in transitions.get(delivery.status, set()):
        raise HTTPException(status_code=409, detail=f"Cannot move a delivery from {delivery.status} to {body.status}.")
    if body.status == "delivered" and not body.proof_url:
        raise HTTPException(status_code=422, detail="Delivery proof is required before marking food delivered.")
    delivery.status = body.status
    if body.proof_url:
        delivery.proof_url = body.proof_url
    donation = db.get(Donation, delivery.donation_id)
    donation.status = body.status
    db.add(DeliveryStatusHistory(delivery_id=delivery.id, actor_id=user.id, status=body.status, note=body.note))
    db.commit()
    db.refresh(delivery)
    return _delivery_json(delivery, db)


@app.post("/deliveries/{delivery_id}/receipt")
def confirm_receipt(
    delivery_id: int,
    user: User = Depends(require_roles("ngo")),
    db: Session = Depends(get_db),
):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None or delivery.ngo_id != user.id:
        raise HTTPException(status_code=404, detail="Delivery not found for this organization.")
    if delivery.status != "delivered":
        raise HTTPException(status_code=409, detail="Receipt can only be confirmed after delivery and proof are recorded.")
    delivery.status = "completed"
    delivery.receipt_confirmed_at = datetime.now(timezone.utc)
    donation = db.get(Donation, delivery.donation_id)
    donation.status = "completed"
    db.add(DeliveryStatusHistory(delivery_id=delivery.id, actor_id=user.id, status="completed", note="Receipt confirmed by receiving organization."))
    db.commit()
    return _delivery_json(delivery, db)


@app.post("/donations/{donation_id}/safety-reports", status_code=201)
def report_safety_issue(
    donation_id: int,
    body: SafetyReportInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found.")
    if user.role != "admin" and user.id not in {donation.donor_id, donation.ngo_id}:
        delivery = db.query(Delivery).filter_by(donation_id=donation_id, volunteer_id=user.id).first()
        if delivery is None:
            raise HTTPException(status_code=403, detail="You are not part of this donation.")
    if donation.status != "completed":
        donation.status = "safety_incident"
        donation.safety_note = body.description
    delivery = db.query(Delivery).filter_by(donation_id=donation_id).first()
    if delivery and delivery.status not in {"completed", "safety_incident"}:
        delivery.status = "safety_incident"
        db.add(DeliveryStatusHistory(delivery_id=delivery.id, actor_id=user.id, status="safety_incident", note=body.description))
    report = SafetyReport(donation_id=donation_id, reporter_id=user.id, description=body.description)
    db.add(report)
    db.commit()
    return {"id": report.id, "status": report.status, "donation_status": donation.status}


@app.get("/admin/safety-reports")
def list_safety_reports(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    reports = db.query(SafetyReport).order_by(SafetyReport.created_at.desc()).limit(200).all()
    return [
        {
            "id": report.id,
            "donation_id": report.donation_id,
            "description": report.description,
            "status": report.status,
            "created_at": _utc(report.created_at).isoformat(),
        }
        for report in reports
    ]


@app.get("/impact")
def impact(db: Session = Depends(get_db)):
    completed = db.query(Donation).filter(Donation.status == "completed").all()
    return {
        "total_donations": db.query(func.count(Donation.id)).scalar() or 0,
        "completed_donations": len(completed),
        "rescued_servings": sum(donation.quantity_servings for donation in completed),
        "estimated_meals": sum(donation.quantity_servings for donation in completed),
        "verified_ngos": db.query(func.count(NGOProfile.id)).filter(NGOProfile.verification_status == "approved").scalar() or 0,
        "active_volunteers": db.query(func.count(VolunteerProfile.id)).filter(VolunteerProfile.available.is_(True)).scalar() or 0,
        "successful_deliveries": len(completed),
        "expired_donations": db.query(func.count(Donation.id)).filter(Donation.status == "expired").scalar() or 0,
        "meals_are_estimated": True,
    }


@app.get("/impact/trends")
def impact_trends(db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=6)
    events = (
        db.query(DeliveryStatusHistory, Donation.quantity_servings)
        .join(Delivery, Delivery.id == DeliveryStatusHistory.delivery_id)
        .join(Donation, Donation.id == Delivery.donation_id)
        .filter(DeliveryStatusHistory.status == "completed")
        .all()
    )
    totals: dict[date, int] = {}
    for event, servings in events:
        event_date = _utc(event.created_at).date()
        if start <= event_date <= today:
            totals[event_date] = totals.get(event_date, 0) + servings
    return [
        {"label": (start + timedelta(days=offset)).strftime("%a"), "meals": totals.get(start + timedelta(days=offset), 0)}
        for offset in range(7)
    ]


@app.get("/admin/users")
def admin_users(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).limit(500).all()
    return [
        {"id": account.id, "name": account.name, "email": account.email, "role": account.role, "is_active": account.is_active}
        for account in users
    ]


@app.post("/admin/users/{user_id}/suspend")
def suspend_user(
    user_id: int,
    suspended: bool,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    account = db.get(User, user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    if account.id == user.id:
        raise HTTPException(status_code=409, detail="Administrators cannot suspend their own account.")
    account.is_active = not suspended
    db.commit()
    return {"id": account.id, "is_active": account.is_active}
