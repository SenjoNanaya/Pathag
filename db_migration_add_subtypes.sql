-- Idempotent migration for legacy databases that predate
-- report_kind/report_subtype/subtype_source and obstacle_verifications.
--
-- Usage:
--   psql "<connection_string>" -f db_migration_add_subtypes.sql

BEGIN;

-- 1) Enum types used by obstacle_reports (match SQLAlchemy Enum class names).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reportkind') THEN
        CREATE TYPE reportkind AS ENUM (
            'obstacle',
            'surface_problem',
            'environmental'
        );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'obstaclesubtype') THEN
        CREATE TYPE obstaclesubtype AS ENUM (
            'parked_vehicle',
            'vendor_stall',
            'construction',
            'flooding',
            'broken_pavement',
            'uneven_surface',
            'missing_curb_cut',
            'stairs_only',
            'other'
        );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subtypesource') THEN
        CREATE TYPE subtypesource AS ENUM (
            'user',
            'ml_suggested'
        );
    END IF;
END
$$;

-- 2) Add missing report columns for legacy obstacle_reports tables.
ALTER TABLE obstacle_reports
    ADD COLUMN IF NOT EXISTS report_kind reportkind NOT NULL DEFAULT 'obstacle',
    ADD COLUMN IF NOT EXISTS report_subtype obstaclesubtype NOT NULL DEFAULT 'other',
    ADD COLUMN IF NOT EXISTS subtype_source subtypesource NOT NULL DEFAULT 'user';

-- 3) Add obstacle_verifications table used by verification_count/LGU exports.
CREATE TABLE IF NOT EXISTS obstacle_verifications (
    id SERIAL PRIMARY KEY,
    obstacle_report_id INTEGER NOT NULL REFERENCES obstacle_reports(id) ON DELETE CASCADE,
    verifier_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_obstacle_verifications_report_verifier
        UNIQUE (obstacle_report_id, verifier_id)
);

CREATE INDEX IF NOT EXISTS ix_obstacle_verifications_obstacle_report_id
    ON obstacle_verifications (obstacle_report_id);

CREATE INDEX IF NOT EXISTS ix_obstacle_verifications_verifier_id
    ON obstacle_verifications (verifier_id);

COMMIT;
