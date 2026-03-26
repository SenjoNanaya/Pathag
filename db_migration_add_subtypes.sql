-- Adds subtype metadata columns for obstacle reports.
-- Run once on the target PostgreSQL database before using the new API fields.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reportkind') THEN
        CREATE TYPE reportkind AS ENUM ('obstacle', 'surface_problem', 'environmental');
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
        CREATE TYPE subtypesource AS ENUM ('user', 'ml_suggested');
    END IF;
END
$$;

ALTER TABLE obstacle_reports
    ADD COLUMN IF NOT EXISTS report_kind reportkind NOT NULL DEFAULT 'obstacle',
    ADD COLUMN IF NOT EXISTS report_subtype obstaclesubtype NOT NULL DEFAULT 'other',
    ADD COLUMN IF NOT EXISTS subtype_source subtypesource NOT NULL DEFAULT 'user';
