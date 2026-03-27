"""
Create Pathag tables on an empty PostgreSQL database (e.g. Supabase).

Prerequisites:
  1. In Supabase SQL Editor run:  CREATE EXTENSION IF NOT EXISTS postgis;
  2. Set DATABASE_URL to your Supabase connection string (direct 5432 recommended).

Usage (from repo root):
  py scripts/init_supabase_schema.py

Safe to re-run: uses checkfirst=True (only creates missing tables).
Does NOT drop data. For a full reset, drop tables in Supabase SQL Editor first.

If you already have an older obstacle_reports table without subtype columns, use
db_migration_add_subtypes.sql instead of or after this script as needed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import Base, engine  # noqa: E402
from app.models import models as _models  # noqa: F401, E402 — registers all tables on Base.metadata
from app.config import settings  # noqa: E402


def main() -> None:
    # Validate DATABASE_URL format early so we can give actionable errors.
    raw = str(settings.DATABASE_URL)
    if not raw.strip():
        raise SystemExit("DATABASE_URL is empty.")

    # Common dotenv pitfalls: unquoted values with '#' and accidental brackets/quotes.
    if any(x in raw for x in ("['", '"]', "['", '"]@')):
        print("ERROR: DATABASE_URL looks like it contains extra bracket/quote characters.")
        print("Check your .env line: make sure you paste the exact Supabase URI.")

    # Print host only (no password).
    try:
        parsed = urlparse(raw)
        host = parsed.hostname
    except ValueError as e:
        print("ERROR: Could not parse DATABASE_URL (urlparse failed).")
        print("This usually means the URI isn't the exact one copied from Supabase.")
        print("Current DATABASE_URL (redacted):")
        redacted = raw
        # Best-effort redaction for `postgresql://user:pass@host/...`
        if "://" in redacted and "@" in redacted:
            prefix, rest = redacted.split("://", 1)
            if ":" in rest:
                userinfo, after = rest.split("@", 1)
                if ":" in userinfo:
                    user, _pass = userinfo.split(":", 1)
                    redacted = f"{prefix}://{user}:***@{after}"
        print(redacted[:300])
        print(f"urlparse error: {e}")
        raise SystemExit(2)

    if not host:
        print("ERROR: Could not extract hostname from DATABASE_URL.")
        print("Paste the exact Supabase connection URI into .env.")
        raise SystemExit(2)

    print(f"DATABASE_URL hostname detected: {host}")
    if "[" in host or "]" in host:
        print("ERROR: DATABASE_URL hostname contains brackets; this usually means your .env value is broken.")
        print("Fix: paste the exact URI from Supabase and wrap it in double-quotes in .env.")
        raise SystemExit(3)

    print("Creating tables from SQLAlchemy models (checkfirst=True)...")
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("Done. Verify in Supabase: Table Editor or SQL:")
    print("  SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1;")


if __name__ == "__main__":
    main()
