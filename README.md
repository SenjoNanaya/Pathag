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
- `POST /api/v1/routes/calculate`
  - accessibility-aware route scoring (prototype)
- `POST /api/v1/obstacles/reports`
- `POST /api/v1/obstacles/reports/{report_id}/verify`
- `POST /api/v1/obstacles/reports/{report_id}/resolve`
- `WS /api/v1/realtime/obstacles/stream`
  - returns obstacle classification and both verifier probabilities
- `POST /api/v1/lgu/heatmap`
  - grid heatmap export for a bbox

Note: `auth` and `users` route modules are currently scaffolds.

## Safety and data quality

- Obstacle reports influence route scoring only after verification threshold is met.
- Temporary obstacle influence expires after `TEMP_OBSTACLE_TTL_HOURS`.
- Image classification responses are advisory (`eligible_for_live_map=false`) until verified.

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
