-- Allow anonymous obstacle reports (no logged-in user). Matches ObstacleReportCreate.reporter_id optional.
-- Safe to run multiple times.
ALTER TABLE obstacle_reports
  ALTER COLUMN reporter_id DROP NOT NULL;
