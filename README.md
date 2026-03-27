# Pathag (Backend + ML + Flutter Prototype)

Pathag is a people-centric navigation prototype focused on pedestrian accessibility.

This repository currently includes:

- FastAPI backend with REST and realtime websocket endpoints
- PostgreSQL + PostGIS data models for users, routes, and obstacle reports
- MobileNetV3-based ML components for:
  - 6-class path condition classification
  - binary obstacle classification
  - binary yes/no verifier gates
- `flutter_app/` prototype client

## Current API surface

Base URL: `http://localhost:8000`

- `POST /api/v1/ml/classify-image`
  - combined image classification (path + obstacle + obstruction gate)
- `GET /api/v1/ml/status`
  - reports if ML is enabled/disabled for the deployment
- `POST /api/v1/routes/calculate`
  - accessibility-aware route scoring (prototype) with optional alternatives payload
- `POST /api/v1/obstacles/reports`
  - accepts `report_kind`, `report_subtype`, and `subtype_source`
- `POST /api/v1/obstacles/reports/{report_id}/verify`
- `POST /api/v1/obstacles/reports/{report_id}/resolve`
- `WS /api/v1/realtime/obstacles/stream`
  - returns obstacle classification and both verifier probabilities
- `POST /api/v1/lgu/heatmap`
  - grid heatmap export for a bbox

Note: `auth` and `users` route modules are currently scaffolds.

## Recent implementation updates

### 1) Demo-safe ML feature flag (backend)

ML can now be disabled for low-resource demo deployments.

- `ML_ENABLED` feature flag added in backend settings.
- ML warmup is skipped when `ML_ENABLED=false`.
- ML route inclusion is conditional.
- Realtime obstacle websocket now returns a clear disabled error when ML is off.
- Added `GET /api/v1/ml/status` for explicit operational visibility.

Recommended `.env` for demo:

```bash
ML_ENABLED=false
ML_WARMUP_ON_STARTUP=false
```

### 2) Route alternatives with backward compatibility

`POST /api/v1/routes/calculate` remains backward compatible:

- Existing clients still use the main route fields:
  - `coordinates`
  - `steps`
  - `accessibility_score`
  - `estimated_duration_seconds`
- New clients can also read:
  - `alternative_routes` (0..N alternatives)

Alternative route schema now supports:

- `distance_meters`
- `estimated_duration_seconds`
- `accessibility_score`
- `coordinates`
- `steps`
- `warnings`
- `force_not_recommended` (optional behavior flag)
- `not_recommended_reasons` (optional UI-ready reasons)

### 3) Forced baseline "not recommended" route

To support explainability in demos, backend now force-includes a baseline route:

- Baseline route = shortest-distance candidate (proxy for pre-report route choice).
- If baseline differs from the selected best route, it is injected into `alternative_routes`.
- Baseline alternative is tagged:
  - `force_not_recommended=true`
  - `not_recommended_reasons=["This route is the shortest-distance baseline before report-aware optimization."]`

This allows frontend to always present a "what you might have taken without report-aware optimization" route.

### 4) Flutter route selection + route quality explanation

`flutter_app/lib/screen/map_page.dart` now supports:

- Route chips in bottom sheet:
  - `Best`, `Alt 1`, `Alt 2` (as available)
- Explicit route selection before navigation starts.
- Selected route updates:
  - map preview line
  - ETA
  - accessibility score
  - obstacle summary chips
- "Not Recommended" labeling for alternatives when:
  - accessibility is lower than Best by >= 5%, or
  - severe conditions are worse than Best (`obstructed`, `no_sidewalk`, `uneven/cracked`)
- Forced backend flag support:
  - if `force_not_recommended=true`, route is always labeled not recommended
  - if backend sends `not_recommended_reasons`, those are shown first
- Why panel examples:
  - `+2 blocked segments`
  - `-7% accessibility`
  - `+3 min longer`

### 5) Hazard visualization rollback

Near-hazard amber band behavior was rolled back to reduce over-flagging:

- Segment highlighting now stays strict to on-path obstacle proximity.
- Near-hazard summary chip removed from map bottom sheet.

## Safety and data quality

- Obstacle reports influence route scoring only after verification threshold is met.
- Temporary obstacle influence expires after `TEMP_OBSTACLE_TTL_HOURS`.
- Image classification responses are advisory (`eligible_for_live_map=false`) until verified.

## Quick DB migration for subtype fields

Before using subtype fields in `/api/v1/obstacles/reports`, run:

```bash
psql <connection_string> -f db_migration_add_subtypes.sql
```

Current subtype list:
- `parked_vehicle`
- `vendor_stall`
- `construction`
- `flooding`
- `broken_pavement`
- `uneven_surface`
- `missing_curb_cut`
- `stairs_only`
- `other`

### Naming and conventions

- Keep naming style in `snake_case` where applicable.
- Keep modular separation across frontend, backend, and database concerns.

## Local setup

1. Create and activate virtual environment:

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env` (optional, defaults exist in `app/config.py`):

```bash
DATABASE_URL=postgresql://pathag:pathag@localhost:5432/pathag
SECRET_KEY=change-me
DEBUG=true

ORS_API_KEY=
ORS_BASE_URL=https://api.openrouteservice.org/v2
ORS_PROFILE=foot-walking
ORS_ALTERNATIVES=3
ORS_REQUEST_TIMEOUT_SECONDS=30

TEMP_OBSTACLE_TTL_HOURS=72
OBSTACLE_VERIFICATION_THRESHOLD=2
OBSTACLE_ROUTE_BUFFER_METERS=50

ML_DEVICE=cpu
ML_ENABLED=true
ML_WARMUP_ON_STARTUP=true
ML_CHECKPOINT_PATH=
OBSTACLE_ML_CHECKPOINT_PATH=
OBSTRUCTION_VERIFIER_ML_CHECKPOINT_PATH=
SURFACE_PROBLEM_VERIFIER_ML_CHECKPOINT_PATH=
OBSTRUCTION_GATE_THRESHOLD=0.5
```

4. Run backend:

```bash
py main.py
```

Swagger: `http://localhost:8000/docs`

## ML training scripts

All scripts are under `ml_service/`.

### Path condition model (6 classes)

Expected class folders:

- `smooth`
- `cracked`
- `uneven`
- `obstructed`
- `no_sidewalk`
- `under_construction`

Train:

```bash
python ml_service/train.py --train_dir <path_dataset/train> --val_dir <path_dataset/val>
```

### Obstacle model (binary yes/no)

Expected class folders:

- `yes`
- `no`

Train:

```bash
python ml_service/obstacle_train.py --train_dir <obstacle_dataset/train> --val_dir <obstacle_dataset/val>
```

### Binary verifier model (yes/no)

Expected class folders:

- `yes`
- `no`

Train:

```bash
python ml_service/binary_verifier_train.py --train_dir <verifier_dataset/train> --val_dir <verifier_dataset/val>
```

## Project Sidewalk dataset preparation

### Surface-problem verifier dataset

Builds `yes` / `no` folders:

```bash
python ml_service/prepare_projectsidewalk_path_dataset.py --output_dir surface_problem_verifier_dataset
```

### Obstacle verifier dataset

Builds `yes` / `no` folders:

```bash
python ml_service/prepare_projectsidewalk_obstacle_dataset.py --output_dir obstacle_verifier_dataset
```

Optional filter to keep only positives:

```bash
python ml_service/prepare_projectsidewalk_obstacle_dataset.py --output_dir obstacle_verifier_dataset --only_yes
```

Notes:

- This script now emits the unified binary schema directly (`yes` / `no`).

## Flutter prototype

`flutter_app/` contains a prototype client that can call routing and obstacle-related backend endpoints.
Adjust backend base URL in `flutter_app/lib/screen/map_page.dart` as needed.

## Deployment notes

- Fly.io + Supabase deployment guides:
  - `docs/DEPLOY_FLY_SUPABASE.md`
  - `docs/DEPLOY_RENDER_SUPABASE.md`
- If using Supabase Postgres from scratch, initialize schema with:

```bash
python scripts/init_supabase_schema.py
```
