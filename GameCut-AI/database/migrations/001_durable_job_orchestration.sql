-- Apply once to existing GameCut AI installations.
-- Requires MySQL 8.0+ or a compatible MariaDB release with JSON support.

ALTER TABLE ai_jobs
    ADD COLUMN execution_token VARCHAR(128) NULL AFTER max_attempts,
    ADD COLUMN leased_by VARCHAR(120) NULL AFTER execution_token,
    ADD COLUMN lease_expires_at TIMESTAMP NULL AFTER leased_by,
    ADD COLUMN heartbeat_at TIMESTAMP NULL AFTER lease_expires_at,
    ADD COLUMN pipeline_version VARCHAR(64) NOT NULL DEFAULT 'v1' AFTER heartbeat_at,
    ADD COLUMN input_sha256 CHAR(64) NULL AFTER pipeline_version,
    ADD COLUMN cancel_requested_at TIMESTAMP NULL AFTER input_sha256,
    ADD COLUMN delete_requested_at TIMESTAMP NULL AFTER cancel_requested_at,
    ADD COLUMN superseded_by_job_id INT NULL AFTER delete_requested_at,
    ADD INDEX idx_lease_expiry (status, lease_expires_at),
    ADD INDEX idx_execution_token (execution_token),
    ADD CONSTRAINT fk_ai_jobs_superseded_by
        FOREIGN KEY (superseded_by_job_id) REFERENCES ai_jobs(id) ON DELETE SET NULL;

ALTER TABLE projects
    ADD COLUMN delete_requested_at TIMESTAMP NULL AFTER completed_at,
    ADD INDEX idx_delete_requested (delete_requested_at);

CREATE TABLE ai_job_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    job_id INT NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    previous_status VARCHAR(32) NULL,
    status VARCHAR(32) NULL,
    progress INT NULL,
    step VARCHAR(255) NULL,
    message VARCHAR(1000) NULL,
    details JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES ai_jobs(id) ON DELETE CASCADE,
    INDEX idx_job_created (job_id, created_at),
    INDEX idx_event_type_created (event_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- `processing_status` is legacy duplicate state. Keep it temporarily for old
-- installs, then drop it only after all consumers use ai_jobs + ai_job_events.
