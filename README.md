# Pathag (Backend + ML Prototype)

Pathag is a people-centric navigation backend prototype focused on **pedestrian accessibility**. This repository currently contains:

- A **FastAPI** backend (REST API)
- **PostgreSQL + PostGIS** data models for users, path segments, obstacle reports, validations, and cached routes
- A **MobileNetV3 (PyTorch)** image classifier that predicts sidewalk/path surface condition
- A **prototype routing service** that generates demo routes and computes an accessibility score using nearby obstacle reports

## What’s implemented vs intended

- **Implemented**
  - Image classification endpoint that returns **transparent probabilities and narrative reasons**
  - Route calculation endpoint (prototype): returns coordinates, steps, warnings, accessibility score, and narrative reasons
  - Auth endpoints (register/login) using JWT
  - Verified-only + decay logic for temporary obstacle reports **when scoring routes**
- **Not implemented yet (planned)**
  - OpenRouteService (ORS) integration and a full weighted cost model based on real network routing
  - Obstacle reporting + multi-user verification workflows (human-in-the-loop moderation endpoints)
  - LGU “heatmaps of inaccessibility” exports
  - Flutter mobile app (not part of this repo right now)

## API overview

Base URL: `http://localhost:8000`

### ML
- `POST /api/v1/ml/classify-image`
  - Upload an image (`multipart/form-data` field: `file`)
  - Returns both:
    - path surface classification (`path_condition`, `confidence`, `probabilities`, `narrative_reasons`)
    - obstacle classification (`obstacle_type`, `confidence`, `probabilities`, `narrative_reasons`)
  - Note: Output is **not eligible for live map updates** without human verification

### Auth
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`

### Users
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`

### Routes (prototype)
- `POST /api/v1/routes/calculate`
  - Input: origin/destination, accessibility preferences, optional `walking_speed_mps`
  - Output: coordinates + steps + warnings + `narrative_reasons`

## Privacy + safety rules enforced in code

- **Verified-only routing influence**: obstacle reports must be `is_verified=True` to affect route scoring.
- **Temporary obstacle decay**: temporary reports expire after `TEMP_OBSTACLE_TTL_HOURS` (default 72) for routing influence.
- **No sensitive logging for uploads**: the ML route avoids logging identifiers alongside image payloads.

## Local setup

### 1) Create and activate a virtual environment

PowerShell:

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment variables (optional but recommended)

Create a `.env` file in the project root (same folder as `main.py`):

```bash
DATABASE_URL=postgresql://pathag:pathag@localhost:5432/pathag
SECRET_KEY=change-me
ORS_API_KEY=
ML_DEVICE=cpu
ML_CHECKPOINT_PATH=
TEMP_OBSTACLE_TTL_HOURS=72
DEBUG=true
```

### 4) Run the API

```bash
py main.py
```

Then open the interactive docs:

- Swagger UI: `http://localhost:8000/docs`

## Repository structure (current)

- `main.py`: FastAPI app entrypoint
- `app/`
  - `config.py`: settings (env-driven)
  - `database.py`: SQLAlchemy engine/session
  - `models/models.py`: PostGIS + SQLAlchemy models
  - `routes/`: API endpoints (ml/auth/users/routes)
  - `services/`: routing + ML classifier loader
  - `schemas/schemas.py`: Pydantic request/response models
  - `utils/`: auth utilities (JWT/password hashing)
- `ml_service/`: training/inference code for MobileNetV3 path-condition classifier
- `sidewalk_dataset/`: placeholder dataset folders (currently `.gitkeep` only)

## Notes / limitations

- The routing service is still a **prototype**; it does not yet call ORS and does not yet compute true network paths.
- Database migrations (Alembic) are not wired up yet in this repo.