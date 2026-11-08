from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Donation, User
from app.security import hash_password


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestingSession() as db:
        db.add(User(name="Platform Admin", email="admin@foodbridge.org", password_hash=hash_password("safe-passphrase-42"), role="admin"))
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def register(client, name, email, role, organization_name=None):
    return client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": "safe-passphrase-42",
            "role": role,
            "organization_name": organization_name,
        },
    )


def token_headers(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_complete_donation_workflow_and_verified_impact(client):
    donor = register(client, "Green Table", "donor@example.org", "donor")
    ngo = register(client, "Community Kitchen", "ngo@example.org", "ngo", "Community Kitchen Trust")
    volunteer = register(client, "Asha Volunteer", "volunteer@example.org", "volunteer")
    alternate_volunteer = register(client, "Ravi Volunteer", "ravi@example.org", "volunteer")
    donor_headers = token_headers(donor)
    ngo_headers = token_headers(ngo)
    volunteer_headers = token_headers(volunteer)
    admin_headers = {"Authorization": f"Bearer {client.post('/auth/login', json={'email': 'admin@foodbridge.org', 'password': 'safe-passphrase-42'}).json()['access_token']}"}

    assert client.put(
        "/ngo/profile",
        headers=ngo_headers,
        json={
            "service_area": "Central Bengaluru",
            "accepted_categories": ["prepared meals"],
            "receiving_capacity": 50,
            "latitude": 12.98,
            "longitude": 77.60,
        },
    ).status_code == 200
    assert client.post(f"/admin/ngos/{ngo.json()['user']['id']}/review?decision=approved", headers=admin_headers).status_code == 200
    assert client.put(
        "/volunteer/profile",
        headers=volunteer_headers,
        json={"phone": "+91 98765 43210", "available": True, "service_area": "Central Bengaluru", "latitude": 12.9716, "longitude": 77.5946},
    ).status_code == 200
    alternate_headers = token_headers(alternate_volunteer)
    assert client.put(
        "/volunteer/profile",
        headers=alternate_headers,
        json={"phone": "+91 98765 43211", "available": True, "service_area": "Central Bengaluru", "latitude": 12.972, "longitude": 77.595},
    ).status_code == 200
    volunteer_id = volunteer.json()["user"]["id"]
    alternate_volunteer_id = alternate_volunteer.json()["user"]["id"]
    assert client.post(f"/admin/volunteers/{volunteer_id}/review?decision=approved", headers=admin_headers).status_code == 200
    assert client.post(f"/admin/volunteers/{alternate_volunteer_id}/review?decision=approved", headers=admin_headers).status_code == 200
    volunteer_applications = client.get("/admin/volunteers", headers=admin_headers)
    assert volunteer_applications.status_code == 200
    assert all(application["verification_status"] == "approved" for application in volunteer_applications.json())

    now = datetime.now(timezone.utc)
    posted = client.post(
        "/donations",
        headers=donor_headers,
        json={
            "title": "Fresh lunch boxes",
            "category": "prepared meals",
            "quantity_servings": 40,
            "prepared_at": (now - timedelta(hours=1)).isoformat(),
            "pickup_deadline": (now + timedelta(hours=3)).isoformat(),
            "storage_method": "Chilled at 4°C",
            "allergens": "Contains dairy",
            "packaging_condition": "Sealed containers",
            "pickup_address": "12 Market Road, Bengaluru",
            "latitude": 12.9716,
            "longitude": 77.5946,
        },
    )
    assert posted.status_code == 201
    donation_id = posted.json()["id"]
    recommendations = client.get(f"/donations/{donation_id}/matches", headers=donor_headers)
    assert recommendations.status_code == 200
    assert recommendations.json()[0]["organization_name"] == "Community Kitchen Trust"
    assert recommendations.json()[0]["verification_status"] == "approved"

    accepted = client.post(f"/donations/{donation_id}/accept", headers=ngo_headers)
    assert accepted.status_code == 201
    delivery_id = accepted.json()["id"]
    assert client.post(f"/donations/{donation_id}/accept", headers=ngo_headers).status_code == 409
    assert client.post(
        f"/deliveries/{delivery_id}/assign",
        headers=ngo_headers,
        json={"volunteer_id": volunteer.json()["user"]["id"]},
    ).status_code == 201
    assert client.post(f"/deliveries/{delivery_id}/accept-task", headers=volunteer_headers).status_code == 200
    assert client.post(f"/deliveries/{delivery_id}/status", headers=volunteer_headers, json={"status": "failed_pickup"}).status_code == 200
    recommendations = client.get(f"/volunteers/recommendations/{delivery_id}", headers=ngo_headers)
    assert recommendations.status_code == 200
    assert [item["volunteer_id"] for item in recommendations.json()] == [alternate_volunteer.json()["user"]["id"]]
    assert client.post(
        f"/deliveries/{delivery_id}/assign",
        headers=ngo_headers,
        json={"volunteer_id": alternate_volunteer.json()["user"]["id"]},
    ).status_code == 201
    assert client.post(f"/deliveries/{delivery_id}/accept-task", headers=alternate_headers).status_code == 200
    assert client.post(f"/deliveries/{delivery_id}/status", headers=alternate_headers, json={"status": "pickup_confirmed"}).status_code == 200
    assert client.post(f"/deliveries/{delivery_id}/status", headers=alternate_headers, json={"status": "in_transit"}).status_code == 200
    assert client.post(f"/deliveries/{delivery_id}/status", headers=alternate_headers, json={"status": "delivered"}).status_code == 422
    assert client.post(
        f"/deliveries/{delivery_id}/status",
        headers=alternate_headers,
        json={"status": "delivered", "proof_url": "https://example.test/receipt.jpg"},
    ).status_code == 200
    assert client.get("/impact").json()["rescued_servings"] == 0
    assert client.post(f"/deliveries/{delivery_id}/receipt", headers=ngo_headers).status_code == 200
    result = client.get("/impact").json()
    assert result["completed_donations"] == 1
    assert result["rescued_servings"] == 40
    assert result["meals_are_estimated"] is True
    unsafe_donation = client.post(
        "/donations",
        headers=donor_headers,
        json={
            "title": "Donation with a reported concern",
            "category": "prepared meals",
            "quantity_servings": 8,
            "prepared_at": (now - timedelta(hours=1)).isoformat(),
            "pickup_deadline": (now + timedelta(hours=3)).isoformat(),
            "storage_method": "Chilled",
            "packaging_condition": "Sealed containers",
            "pickup_address": "12 Market Road, Bengaluru",
            "latitude": 12.9716,
            "longitude": 77.5946,
        },
    ).json()
    report = client.post(
        f"/donations/{unsafe_donation['id']}/safety-reports",
        headers=donor_headers,
        json={"description": "Packaging was damaged during storage."},
    )
    assert report.status_code == 201
    assert client.get(f"/donations/{unsafe_donation['id']}/matches", headers=donor_headers).json() == []
    assert client.post(f"/donations/{unsafe_donation['id']}/accept", headers=ngo_headers).status_code == 409
    timeline = client.get("/deliveries", headers=donor_headers).json()[0]["history"]
    assert [item["status"] for item in timeline] == [
        "accepted",
        "volunteer_assigned",
        "volunteer_accepted",
        "failed_pickup",
        "volunteer_assigned",
        "volunteer_accepted",
        "pickup_confirmed",
        "in_transit",
        "delivered",
        "completed",
    ]


def test_unverified_ngo_cannot_accept_and_roles_are_enforced(client):
    donor = register(client, "Green Table", "donor2@example.org", "donor")
    ngo = register(client, "New Kitchen", "ngo2@example.org", "ngo")
    headers = token_headers(donor)
    now = datetime.now(timezone.utc)
    donation = client.post(
        "/donations",
        headers=headers,
        json={
            "title": "Extra bread",
            "category": "bakery",
            "quantity_servings": 12,
            "prepared_at": (now - timedelta(hours=1)).isoformat(),
            "pickup_deadline": (now + timedelta(hours=2)).isoformat(),
            "storage_method": "Room temperature",
            "packaging_condition": "Sealed",
            "pickup_address": "12 Market Road, Bengaluru",
            "latitude": 12.9716,
            "longitude": 77.5946,
        },
    ).json()
    assert client.get(f"/donations/{donation['id']}/matches", headers=headers).json() == []
    assert client.post(f"/donations/{donation['id']}/accept", headers=token_headers(ngo)).status_code == 403
    assert client.put(
        "/ngo/profile",
        headers=token_headers(donor),
        json={
            "service_area": "Central Bengaluru",
            "accepted_categories": ["prepared meals"],
            "receiving_capacity": 50,
            "latitude": 12.98,
            "longitude": 77.60,
        },
    ).status_code == 403
    assert client.get("/admin/ngos", headers=token_headers(donor)).status_code == 403


def test_expired_donations_are_not_matchable_or_acceptable(client):
    donor = register(client, "Green Table", "donor3@example.org", "donor")
    headers = token_headers(donor)
    now = datetime.now(timezone.utc)
    response = client.post(
        "/donations",
        headers=headers,
        json={
            "title": "Yesterday's surplus",
            "category": "prepared meals",
            "quantity_servings": 12,
            "prepared_at": (now - timedelta(hours=4)).isoformat(),
            "pickup_deadline": (now - timedelta(hours=1)).isoformat(),
            "storage_method": "Chilled",
            "packaging_condition": "Sealed",
            "pickup_address": "12 Market Road, Bengaluru",
            "latitude": 12.9716,
            "longitude": 77.5946,
        },
    )
    assert response.status_code == 422


def test_stale_listings_are_marked_expired_when_loaded(client):
    donor = register(client, "Green Table", "donor4@example.org", "donor")
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    now = datetime.now(timezone.utc)
    donation = Donation(
        donor_id=donor.json()["user"]["id"],
        title="Past its collection deadline",
        category="prepared meals",
        quantity_servings=10,
        prepared_at=now - timedelta(hours=4),
        pickup_deadline=now - timedelta(hours=1),
        storage_method="Chilled",
        allergens="Not specified",
        packaging_condition="Sealed",
        pickup_address="12 Market Road, Bengaluru",
        latitude=12.9716,
        longitude=77.5946,
    )
    db.add(donation)
    db.commit()
    generator.close()
    response = client.get("/donations", headers=token_headers(donor))
    assert response.status_code == 200
    assert response.json()[0]["status"] == "expired"
