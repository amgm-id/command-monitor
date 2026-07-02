-- ServerAgent Monitor - Database Schema Reference
-- This is for reference only. Tables are auto-created by SQLAlchemy.
-- The application creates all tables on first startup.

-- ============================================================
-- USERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(50)  UNIQUE NOT NULL,
    email       VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name   VARCHAR(100),
    role        VARCHAR(20)  NOT NULL DEFAULT 'viewer',
    -- role: super_admin | admin | auditor | viewer
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login  TIMESTAMP
);

-- ============================================================
-- SERVERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS servers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(100) NOT NULL,
    hostname      VARCHAR(255) NOT NULL,
    ip_address    VARCHAR(45)  NOT NULL,
    agent_token   VARCHAR(128) UNIQUE NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    last_seen     TIMESTAMP,
    os_info       JSONB,
    agent_version VARCHAR(20),
    total_commands INTEGER NOT NULL DEFAULT 0,
    description   VARCHAR(500),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- COMMAND LOGS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS command_logs (
    id           BIGSERIAL PRIMARY KEY,
    server_id    UUID REFERENCES servers(id) ON DELETE SET NULL,
    username     VARCHAR(50)  NOT NULL,
    remote_ip    VARCHAR(45),
    terminal     VARCHAR(30),
    working_dir  VARCHAR(500),
    command      TEXT NOT NULL,
    exit_code    INTEGER,
    risk_level   VARCHAR(20)  NOT NULL DEFAULT 'low',
    -- risk_level: low | medium | high | critical
    risk_reason  TEXT,
    session_id   VARCHAR(100),
    timestamp    TIMESTAMP NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_command_logs_server_timestamp ON command_logs(server_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_command_logs_username_timestamp ON command_logs(username, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_command_logs_risk_level ON command_logs(risk_level);
CREATE INDEX IF NOT EXISTS ix_command_logs_timestamp ON command_logs(timestamp DESC);

-- ============================================================
-- SESSION LOGS TABLE (login history)
-- ============================================================
CREATE TABLE IF NOT EXISTS session_logs (
    id            BIGSERIAL PRIMARY KEY,
    server_id     UUID REFERENCES servers(id) ON DELETE SET NULL,
    username      VARCHAR(50)  NOT NULL,
    remote_ip     VARCHAR(45),
    terminal      VARCHAR(30),
    login_time    TIMESTAMP    NOT NULL,
    logout_time   TIMESTAMP,
    duration      INTEGER,        -- seconds
    login_method  VARCHAR(20) NOT NULL DEFAULT 'unknown',
    -- login_method: ssh | console | su | sudo | unknown
    status        VARCHAR(20) NOT NULL DEFAULT 'active',
    -- status: active | ended | failed | timeout
    failed_reason VARCHAR(255),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_session_logs_server_login ON session_logs(server_id, login_time DESC);
CREATE INDEX IF NOT EXISTS ix_session_logs_username ON session_logs(username);
CREATE INDEX IF NOT EXISTS ix_session_logs_status ON session_logs(status);

-- ============================================================
-- ACTIVE SESSIONS TABLE (real-time current sessions)
-- ============================================================
CREATE TABLE IF NOT EXISTS active_sessions (
    id               BIGSERIAL PRIMARY KEY,
    server_id        UUID NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    session_log_id   BIGINT REFERENCES session_logs(id) ON DELETE SET NULL,
    username         VARCHAR(50) NOT NULL,
    remote_ip        VARCHAR(45),
    terminal         VARCHAR(30),
    login_time       TIMESTAMP NOT NULL,
    idle_time        VARCHAR(20),
    current_process  TEXT,
    pid              INTEGER,
    updated_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_active_sessions_server ON active_sessions(server_id);

-- ============================================================
-- ALERTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id                  BIGSERIAL PRIMARY KEY,
    server_id           UUID REFERENCES servers(id) ON DELETE SET NULL,
    command_log_id      BIGINT REFERENCES command_logs(id) ON DELETE SET NULL,
    username            VARCHAR(50) NOT NULL,
    remote_ip           VARCHAR(45),
    command             TEXT NOT NULL,
    risk_level          VARCHAR(20) NOT NULL,
    risk_reason         TEXT,
    is_acknowledged     BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    acknowledged_at     TIMESTAMP,
    timestamp           TIMESTAMP NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_alerts_unacknowledged ON alerts(is_acknowledged) WHERE is_acknowledged = FALSE;
CREATE INDEX IF NOT EXISTS ix_alerts_server_timestamp ON alerts(server_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_alerts_risk_level ON alerts(risk_level);

-- ============================================================
-- AUDIT TRAIL TABLE (web app actions)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_trail (
    id            BIGSERIAL PRIMARY KEY,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    action        VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id   VARCHAR(100),
    details       JSONB,
    ip_address    VARCHAR(45),
    user_agent    VARCHAR(255),
    timestamp     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_trail_user ON audit_trail(user_id);
CREATE INDEX IF NOT EXISTS ix_audit_trail_timestamp ON audit_trail(timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_audit_trail_action ON audit_trail(action);
