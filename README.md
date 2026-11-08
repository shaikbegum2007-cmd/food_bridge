# FoodBridge

FoodBridge connects food donors, verified NGOs, volunteers, and platform administrators through a responsive food-rescue workflow.

## What works

- Role-aware registration, password hashing, signed expiring access tokens, and protected API routes.
- NGO application review by an administrator; only approved NGOs can accept a donation.
- Volunteer profiles with phone, service area, availability, and administrator approval before task assignment.
- Donation listings with food category, servings, preparation time, pickup deadline, storage, allergens, packaging, address, coordinates, and an optional photo URL.
- Database-backed NGO matching with configurable weights for distance, urgency, quantity, category, and nearby volunteer availability. Expired, incompatible, unverified, overloaded, or distant NGOs are excluded.
- Atomic donation acceptance, volunteer recommendations and assignment, task acceptance, a persistent delivery timeline, proof-link requirement, and NGO-only receipt confirmation.
- Delivery routes link to Google Maps, show approximate distance and estimated travel time, and refresh delivery status every 15 seconds.
- Safety reports immediately put unfinished donations on hold. Expired listings are marked by a background worker and on listing/matching requests.
- Impact figures count only deliveries whose receiving NGO confirmed receipt. Meal counts are clearly identified as estimates.
- Responsive role-specific dashboards, PostgreSQL Docker Compose configuration, a private administrator bootstrap command, and integration tests.

## Run locally

### Option A: Docker Compose (PostgreSQL, API, and web app)

1. Install and start Docker Desktop.
2. From the project root, run:

   ```powershell
   docker compose up --build
   ```

3. Open `http://localhost:5173` for the application and `http://localhost:8000/docs` for the API.
4. Create an administrator in another terminal:

   ```powershell
   docker compose exec api python -m app.create_admin
   ```

For anything other than a throwaway local environment, set strong `POSTGRES_PASSWORD` and `JWT_SECRET` values in a local `.env` file. Do not commit `.env`.

### Option B: Run without Docker

Start PostgreSQL and create an empty `foodbridge` database, then set `DATABASE_URL`, `JWT_SECRET`, and `CORS_ORIGINS` in your PowerShell session. For a quick local prototype, omit `DATABASE_URL` to use SQLite. Apply the schema before starting the API:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r backend\requirements.txt
py -m alembic -c backend\alembic.ini upgrade head
py -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
npm.cmd install
npm.cmd run dev
```

The Vite development server proxies API requests to `http://127.0.0.1:8000`. Keep the backend running in its terminal while using the web app. To create an admin in a third terminal, use the backend virtual environment and run `py -m backend.app.create_admin` from the project root.

## Demonstration workflow

1. Create a donor, NGO, and volunteer account from the registration screen.
2. Create an admin using the bootstrap command and sign in as that administrator.
3. Approve the NGO in **NGO verification**.
4. Sign in as the NGO and set its categories, receiving capacity, service area, and coordinates under **Organization profile**.
5. Set volunteer phone, availability, service area, and location under **My profile**. An administrator approves the volunteer under **Volunteer management**.
6. As the donor, post a donation with a future pickup deadline and valid pickup coordinates.
7. Review **Smart matches** as the donor. As the approved NGO, accept the listing under **Nearby food**.
8. Assign a recommended volunteer from **Deliveries**. The volunteer accepts, confirms pickup, marks transit, and provides an HTTPS proof link.
9. The receiving NGO confirms receipt. Only then does the completed donation count toward rescued servings.

## Tests and migrations

From the project root:

```powershell
py -m pip install -r backend\requirements.txt
py -m pytest backend\tests -q
py -m alembic -c backend\alembic.ini upgrade head
```

When using PostgreSQL, set `DATABASE_URL` to the PostgreSQL connection string before running Alembic. The API expects the Alembic schema to be applied before startup. Docker Compose applies migrations before launching the API.

## Important limitations

This is a working MVP, not a production-ready food-safety, identity-verification, or logistics service. NGO and volunteer verification are administrator decisions in the app; document upload/storage, email or push notifications, geocoding, actual photo upload, audit-log review, rate limiting, and WebSocket notifications still need production implementations. Delivery updates are polled every 15 seconds. Google Maps links use entered addresses and coordinates; distance and travel-time figures are approximate. Donation photo and delivery-proof fields currently accept links; operators must verify evidence and food handling in person. The app does not decide food safety from a photo or claim FSSAI compliance. Configure secure production secrets, HTTPS, storage, retention/privacy controls, monitoring, and operational procedures before a real-world pilot.
