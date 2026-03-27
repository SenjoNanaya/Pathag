# Deploy Pathag API on Render with Supabase (Postgres + PostGIS)

This guide wires the FastAPI backend to **Supabase PostgreSQL** (with **PostGIS**) and runs the app on **Render**. Your Flutter app or Swagger should call the Render URL (HTTPS).

## 1. Supabase: database

1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** and enable PostGIS (required for `Geometry` / routing):

   ```sql
   create extension if not exists postgis;
   ```

3. **Apply the Pathag schema** (pick one path).

   ### Fresh Supabase project (no tables yet) — recommended

   Tables are defined in SQLAlchemy (`app/models/models.py`); there is no single `schema.sql` in the repo.

   1. Keep step 2 (`postgis` extension) done.
   2. On your machine, point `DATABASE_URL` at Supabase (same URI you will use in production):
      - Copy **Settings → Database → Connection string → URI** (direct `5432` is easiest for this one-off script).
      - Put it in project-root `.env` as `DATABASE_URL=...` or export it in the shell.
   3. From the **repository root** (with venv active and `pip install -r requirements.txt` already done):

      ```bash
      py scripts/init_supabase_schema.py
      ```

      This runs `Base.metadata.create_all(..., checkfirst=True)` and creates, among others:
      `users`, `path_segments`, `obstacle_reports`, `path_validations`, `routes`, `obstacle_verifications`.

   4. **Reporter column (optional SQL):** If you ever created `obstacle_reports` before `reporter_id` was nullable, run:

      ```bash
      psql "<your-supabase-uri>" -f db_migration_reporter_id_nullable.sql
      ```

      On a brand-new DB created only via the script above, `reporter_id` is already nullable — you can skip this.

   5. **Do not** run `db_migration_add_subtypes.sql` on a brand-new DB created by `init_supabase_schema.py` unless you know you need it — that migration targets **older** databases that lacked `report_kind` / `report_subtype` / `subtype_source`. The init script already creates those columns from the models.

   ### Migrating from an existing local Postgres

   Use a schema + data dump instead of the Python script, for example:

   ```bash
   pg_dump "postgresql://pathag:pathag@localhost:5432/pathag" --no-owner --no-acl -F p -f pathag_dump.sql
   ```

   Then in Supabase **SQL Editor**, run PostGIS (`create extension if not exists postgis;`) first, then apply the dump in chunks or via `psql` against the Supabase URI. Review the dump for roles/extensions Supabase does not allow.

4. Get the **connection string**:
   - **Project Settings → Database → Connection string → URI**.
   - Prefer the **direct** connection (port **5432**) for a long-lived Render web service (simpler than PgBouncer transaction pooling with SQLAlchemy).
   - The URI often already includes `?sslmode=require`. If it does, you can set `DATABASE_SSL_REQUIRE=false` on Render to avoid duplicate SSL hints; if the URI has no SSL params, set `DATABASE_SSL_REQUIRE=true`.
   - If Render logs show connection timeouts, check Supabase **IPv4** / pooler options ([Supabase connecting docs](https://supabase.com/docs/guides/database/connecting-to-postgres))—some hosts need the pooler hostname instead of direct DB.

5. **Optional:** Import path data (e.g. OSM import script) against this database once tables exist.

## 2. Render: web service

### Option A — Blueprint (recommended)

1. Commit `Dockerfile`, `render.yaml`, and this repo to GitHub/GitLab.
2. In Render: **New → Blueprint**, select the repo, confirm `render.yaml`.
3. In the Render dashboard for `pathag-api`, set **Environment** secrets:
   - `DATABASE_URL` — paste the Supabase URI (mask password in UI only; value is secret).
   - `SECRET_KEY` — long random string (you can keep Render-generated or replace).
   - `ORS_API_KEY` — if you use OpenRouteService.
   - `PUBLIC_API_BASE_URL` — your public API base, e.g. `https://pathag-api.onrender.com` (for planning CSV image links).

4. Deploy. Render runs:

   `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. Health check: `GET /health` (configured in `render.yaml`).

### Option B — Manual Docker service

1. **New → Web Service**, connect repo, **Environment → Docker**, `Dockerfile` at repo root.
2. Set the same env vars as above.

### Option B2 — Native Python (no Docker)

Build command: `pip install -r requirements.txt`  
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`  

Note: **PyTorch** in `requirements.txt` is large; Docker or a paid plan with a longer build may be more reliable than the free native build.

## 3. Environment variables (reference)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Supabase Postgres URI |
| `DATABASE_SSL_REQUIRE` | `true` if URI has no `sslmode=require` |
| `SECRET_KEY` | JWT / auth signing |
| `DEBUG` | `false` in production |
| `ORS_API_KEY` | OpenRouteService |
| `PUBLIC_API_BASE_URL` | Public `https://…` origin for exports / image URLs |
| `ML_WARMUP_ON_STARTUP` | `false` on small instances; ML loads on first use |
| `UPLOAD_DIR` | Default `./uploads` (ephemeral on Render; see below) |

## 4. Operational caveats

- **Disk:** Render’s filesystem is **ephemeral**. Files under `./uploads` are lost on redeploy/restart. For production evidence photos, plan **Supabase Storage** or S3 and store URLs in `image_url`.
- **Memory:** PyTorch + MobileNet is heavy. **Starter** (512 MB) may OOM when ML runs. Use a larger instance or keep `ML_WARMUP_ON_STARTUP=false` and accept a slow first ML request; if it still fails, upgrade the plan.
- **CORS:** `main.py` currently allows `*`. For production you may restrict `allow_origins` to your Flutter web domain.

## 5. Verify

- Open `https://<your-service>.onrender.com/docs`
- `GET /health` → `{"status":"ok"}`
- Run a simple DB-backed route (e.g. list obstacles or compute route) from Swagger.

## 6. Flutter / mobile

Use your **Render HTTPS URL** as the API base (not `localhost`). For Android emulator, `10.0.2.2` only applies to the host machine, not Render.
