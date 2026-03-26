# Pathag (Backend + ML + Flutter Prototype)

Pathag is a people-centric navigation prototype focused on **pedestrian accessibility**.

This repository currently contains:

- A **FastAPI** backend (REST + websocket)
- **PostgreSQL + PostGIS** data models for users, path segments, obstacle reports, verifications, and routes
- **MobileNetV3 (PyTorch)** classifiers:
  - path-condition classifier
  - obstacle-type classifier
  - binary verifiers (obstruction present/absent, surface-problem present/absent)
- A route calculation service with:
  - fallback demo routing
  - optional ORS route alternatives
  - obstacle-aware accessibility scoring
- A `flutter_app/` prototype client

## Current status (implemented)

- Path image classification endpoint with transparent probabilities and narrative reasons
- Obstacle image classification endpoint with transparent probabilities and narrative reasons
- Route calculation endpoint (`/api/v1/routes/calculate`)
- Obstacle reporting workflow:
  - create report
  - verify report (multi-user confirmation threshold)
  - resolve report
- Realtime obstacle websocket:
  - obstacle-type classifier output
  - obstruction verifier output
  - surface-problem verifier output
  - `suggested_report_kind` and `suggested_obstacle_type` for client-side automation
- LGU heatmap export endpoint (`/api/v1/lgu/heatmap`)
- Verified-only + temporary-obstacle TTL logic for route scoring

## Known gaps / limitations

- `auth.py` and `users.py` routers are currently scaffolds (auth/user endpoints are not fully wired).
- ORS integration is best-effort/optional and falls back to demo routing.
- Route scoring is heuristic, not a full production cost model yet.
- No Alembic migration workflow is currently wired.

## API overview

Base URL: `http://localhost:8000`

### ML endpoints

- `POST /api/v1/ml/classify-path-image`
- `POST /api/v1/ml/classify-obstacle-image`

Both endpoints accept `multipart/form-data` with `file`.

### Routes

- `POST /api/v1/routes/calculate`
  - Input: origin/destination + optional accessibility preferences
  - Output: distance, duration, accessibility score, coordinates, steps, warnings

### Obstacles (human-in-the-loop)

- `POST /api/v1/obstacles/reports`
- `POST /api/v1/obstacles/reports/{report_id}/verify`
- `POST /api/v1/obstacles/reports/{report_id}/resolve`

### Realtime websocket

- `WS /api/v1/realtime/obstacles/stream`
  - Input message:
    - `image_base64`
    - `latitude`
    - `longitude`
  - Output includes:
    - obstacle classifier output
    - obstruction verifier output
    - surface-problem verifier output
    - `suggested_report_kind` (`obstacle`, `surface_problem`, `none`)
    - `suggested_obstacle_type`

### LGU reporting

- `POST /api/v1/lgu/heatmap`
  - Input: bounding box + grid cell size
  - Output: `LGUReportResponse` with heatmap points

## Safety / data-quality rules in code

- Route scoring only uses `is_verified=True` obstacle reports.
- Temporary obstacles decay after `TEMP_OBSTACLE_TTL_HOURS` (default 72).
- ML outputs are advisory and require verification before live-map influence.

## Constitution Alignment

Future code changes must align with the constitution, especially:

- **Never allow unverified high-impact data into live routing.**
  - Keep human-in-the-loop moderation before live map influence.
- **Never keep temporary/ephemeral obstacles forever.**
  - Preserve decay/reverification behavior for trust.
- **Never produce opaque route choices.**
  - Maintain explainability (`narrative_reasons`, route warnings, and scoring rationale).
- **Never hardcode one-size-fits-all mobility assumptions.**
  - Keep threshold and preference parameters configurable.
- **Never store sensitive PII/GPS traces together in logs.**
  - Preserve privacy-safe logging and anonymization behavior.
- **Never return dead-end behavior when all routes are poor.**
  - Prefer least-hazardous fallback output instead of silent failure.

### Requirements style guidance (EARS)

When writing/updating requirements, prefer EARS-style statements:

- Ubiquitous: `THE SYSTEM SHALL ...`
- Event-driven: `WHEN ... THE SYSTEM SHALL ...`
- State-driven: `WHILE ... THE SYSTEM SHALL ...`
- Unwanted: `IF ... THEN THE SYSTEM SHALL ...`

### Naming and conventions

- Keep naming style in `snake_case` where applicable.
- Keep modular separation across frontend, backend, and database concerns.

## Local setup

### 1) Create and activate virtualenv

PowerShell:

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment variables (`.env`)

Example:

```bash
DATABASE_URL=postgresql://pathag:pathag@localhost:5432/pathag
SECRET_KEY=change-me
DEBUG=true

# Routing / ORS
ORS_API_KEY=
ORS_BASE_URL=https://api.openrouteservice.org/v2
ORS_PROFILE=foot-walking
ORS_ALTERNATIVES=3
ORS_REQUEST_TIMEOUT_SECONDS=30

# Scoring / moderation
TEMP_OBSTACLE_TTL_HOURS=72
OBSTACLE_VERIFICATION_THRESHOLD=2
OBSTACLE_ROUTE_BUFFER_METERS=50

# ML
ML_DEVICE=cpu
ML_CHECKPOINT_PATH=
OBSTACLE_ML_CHECKPOINT_PATH=
OBSTRUCTION_VERIFIER_ML_CHECKPOINT_PATH=
SURFACE_PROBLEM_VERIFIER_ML_CHECKPOINT_PATH=
```

### 4) Run backend

```bash
py main.py
```

Swagger: `http://localhost:8000/docs`

## Binary verifier training (Project Sidewalk validator datasets)

These scripts build **binary** verifier datasets (`present` / `absent`) from Project Sidewalk validator datasets:

- `ml_service/prepare_projectsidewalk_obstacle_dataset.py`
- `ml_service/prepare_projectsidewalk_path_dataset.py`

Train with:

```bash
python ml_service/binary_verifier_train.py --train_dir <.../train> --val_dir <.../val> --output <checkpoint_path>
```

## Flutter app

`flutter_app/` contains a prototype map client.

- It can call `/api/v1/routes/calculate`
- It can call websocket realtime obstacle detection
- It can create and verify obstacle reports

Adjust backend base URL in `flutter_app/lib/screen/map_page.dart` as needed.
=======
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
>>>>>>> 9deaef4 (FEAT: Combined both Path Classifier and Object Classifier)
