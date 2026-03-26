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

## Constitution Alignment (YSES Hackfest)

Future code changes must align with the YSES Hackfest constitution (`D:/Download/YSES Hackfest.pdf`), especially:

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