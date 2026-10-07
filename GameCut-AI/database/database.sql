-- GameCut AI Database Schema
-- Run this SQL file in phpMyAdmin or MySQL command line

-- Create database
CREATE DATABASE IF NOT EXISTS gamecut_ai 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE gamecut_ai;

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    description TEXT,
    status ENUM('draft', 'processing', 'completed', 'failed') DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    delete_requested_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_user_status (user_id, status),
    INDEX idx_delete_requested (delete_requested_at),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Videos table
CREATE TABLE IF NOT EXISTS videos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    project_id INT NOT NULL,
    user_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    output_path VARCHAR(500),
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    duration INT DEFAULT 0,
    resolution VARCHAR(50),
    status ENUM('uploaded', 'processing', 'processed', 'failed', 'deleted') DEFAULT 'uploaded',
    processing_started_at TIMESTAMP NULL,
    processing_completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_project_id (project_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_user_status (user_id, status),
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User settings and preferences
CREATE TABLE IF NOT EXISTS user_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL UNIQUE,
    bio TEXT,
    avatar_path VARCHAR(500),
    theme ENUM('light', 'dark', 'system') DEFAULT 'system',
    font_size ENUM('comfortable', 'large', 'compact') DEFAULT 'comfortable',
    compact_mode TINYINT(1) DEFAULT 0,
    accent_color VARCHAR(20) DEFAULT '#7C3AED',
    email_notifications TINYINT(1) DEFAULT 1,
    push_notifications TINYINT(1) DEFAULT 1,
    marketing_updates TINYINT(1) DEFAULT 0,
    two_factor_enabled TINYINT(1) DEFAULT 0,
    language VARCHAR(50) DEFAULT 'English',
    timezone VARCHAR(80) DEFAULT 'Asia/Kolkata',
    currency VARCHAR(10) DEFAULT 'INR',
    default_export VARCHAR(100) DEFAULT 'YouTube Shorts 1080p',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- AI jobs queue table
CREATE TABLE IF NOT EXISTS ai_jobs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    project_id INT NOT NULL,
    video_id INT NOT NULL,
    user_id INT NOT NULL,
    job_type VARCHAR(100) NOT NULL DEFAULT 'video_processing',
    status ENUM('queued', 'processing', 'completed', 'failed', 'cancelled') DEFAULT 'queued',
    progress INT DEFAULT 0,
    current_step VARCHAR(255),
    priority TINYINT NOT NULL DEFAULT 5,
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    execution_token VARCHAR(128) NULL,
    leased_by VARCHAR(120) NULL,
    lease_expires_at TIMESTAMP NULL,
    heartbeat_at TIMESTAMP NULL,
    pipeline_version VARCHAR(64) NOT NULL DEFAULT 'v1',
    input_sha256 CHAR(64) NULL,
    cancel_requested_at TIMESTAMP NULL,
    delete_requested_at TIMESTAMP NULL,
    superseded_by_job_id INT NULL,
    payload JSON,
    error_message TEXT,
    available_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (superseded_by_job_id) REFERENCES ai_jobs(id) ON DELETE SET NULL,
    INDEX idx_status_available (status, available_at),
    INDEX idx_lease_expiry (status, lease_expires_at),
    INDEX idx_execution_token (execution_token),
    INDEX idx_project_id (project_id),
    INDEX idx_video_id (video_id),
    INDEX idx_user_id (user_id),
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- `ai_jobs` is the canonical current state. Job events retain the audit trail
-- and make status/progress history observable without a duplicate state table.
CREATE TABLE IF NOT EXISTS ai_job_events (
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

-- Do not ship default accounts. Create the first administrator through a
-- one-time deployment bootstrap using credentials supplied outside this file.
