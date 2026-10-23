-- Run once against an existing GameCut AI database created from an older schema.
-- Safe to run repeatedly with MySQL 8/MariaDB 10.6+.
USE gamecut_ai;

ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS delete_requested_at TIMESTAMP NULL,
    ADD INDEX IF NOT EXISTS idx_delete_requested (delete_requested_at);

ALTER TABLE ai_jobs
    ADD COLUMN IF NOT EXISTS cancel_requested_at TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS delete_requested_at TIMESTAMP NULL,
    ADD INDEX IF NOT EXISTS idx_delete_requested (delete_requested_at);
