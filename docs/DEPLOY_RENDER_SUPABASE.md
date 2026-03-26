# Deploy Pathag API on Render with Supabase (Postgres + PostGIS)

This guide wires the FastAPI backend to **Supabase PostgreSQL** (with **PostGIS**) and runs the app on **Render**. Your Flutter app or Swagger should call the Render URL (HTTPS).

## 1. Supabase: database

1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** and enable PostGIS (required for `Geometry` / routing):

   ```sql
   create extension if not exists postgis;
   ```

3. Apply your schema the same way you did locally, for example:
   - Run any existing SQL migrations (e.g. `db_migration_add_subtypes.sql` and table-creation scripts you use).
   - Ensure enums/tables match `app/models/models.py` (or use Alembic if you have migrations checked in).

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
