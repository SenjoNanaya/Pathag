# Deploy Pathag Backend on Fly.io + Supabase (Postgres + PostGIS)

This uses the existing `Dockerfile` and expects your database to live on **Supabase**.

## 0. Prereqs

1. Create a Fly account and install the CLI: [Fly CLI](https://fly.io/docs/flyctl/install/)
2. Create a Supabase project and enable PostGIS in SQL Editor:

```sql
create extension if not exists postgis;
```

3. Make sure your DB schema exists (tables + enums). Recommended for this repo:

```bash
py scripts/init_supabase_schema.py
```

## 1. Deploy to Fly

From the repo root:

1. Login:

```powershell
flyctl auth login
```

2. Create/deploy:

```powershell
flyctl deploy
```

`fly.toml` in this repo sets:
- Dockerfile build from `./Dockerfile`
- Service listens on internal port `8000`
- Healthcheck uses `GET /health`

## 2. Set secrets (Supabase connection + config)

In Fly, set environment variables as secrets:

```powershell
flyctl secrets set `
  DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require" `
  DATABASE_SSL_REQUIRE="false" `
  SECRET_KEY="change-me-in-prod" `
  DEBUG="false" `
  ML_WARMUP_ON_STARTUP="false" `
  ORS_API_KEY="your-ors-key-or-empty" `
  PUBLIC_API_BASE_URL="https://<your-app>.fly.dev"
```

Notes:
- If your Supabase URI already includes `sslmode=require`, keep `DATABASE_SSL_REQUIRE=false` (avoids double-SSL hints).
- If the URI does **not** include SSL params, set `DATABASE_SSL_REQUIRE=true`.

## 3. Verify

1. Watch deploy:

```powershell
flyctl status
```

2. Open Swagger:

```text
https://<your-app>.fly.dev/docs
```

3. Quick liveness:

```text
https://<your-app>.fly.dev/health
```

## 4. Operational caveats

### Uploads/photos
This backend writes uploaded images to `./uploads` and serves them via `/uploads`.
On Fly, the filesystem can be ephemeral across restarts. For production, use **Supabase Storage** (or persistent volumes) and store the resulting public URLs in `image_url`.

### ML memory
PyTorch can be heavy for small Fly instances. Keeping `ML_WARMUP_ON_STARTUP=false` helps avoid OOM during boot, but first ML calls may be slow.

