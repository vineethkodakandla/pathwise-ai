-- PathWise AI — TimescaleDB Schema
-- Implements: CLAUDE.md Section 6.1 Data Architecture
-- Run via: docker-entrypoint-initdb.d/init.sql

-- ═══════════════════════════════════════════════════════════
--  RAW TELEMETRY (1-second granularity)
--  Req-Func-Sw-1: ≥1 Hz polling frequency
-- ═══════════════════════════════════════════════════════════

CREATE TABLE wan_telemetry (
    time          TIMESTAMPTZ NOT NULL,
    link_id       UUID        NOT NULL,
    site_id       UUID        NOT NULL,
    latency_ms    FLOAT       NOT NULL,
    jitter_ms     FLOAT       NOT NULL,
    packet_loss   FLOAT       NOT NULL,  -- percentage 0.0–100.0
    link_type     VARCHAR(20) NOT NULL   -- FIBER, SATELLITE, 5G, BROADBAND
);
SELECT create_hypertable('wan_telemetry', 'time');
CREATE INDEX ON wan_telemetry (link_id, time DESC);
CREATE INDEX ON wan_telemetry (site_id, time DESC);

-- Backwards-compat alias (existing code uses TEXT link_id)
CREATE TABLE telemetry (
    time        TIMESTAMPTZ NOT NULL,
    link_id     TEXT NOT NULL,
    latency_ms  DOUBLE PRECISION,
    jitter_ms   DOUBLE PRECISION,
    packet_loss_pct DOUBLE PRECISION,
    bandwidth_util_pct DOUBLE PRECISION,
    rtt_ms      DOUBLE PRECISION
);
SELECT create_hypertable('telemetry', 'time');
CREATE INDEX idx_telemetry_link_time ON telemetry (link_id, time DESC);

-- ═══════════════════════════════════════════════════════════
--  CONTINUOUS AGGREGATES (10-second rollups for model training)
-- ═══════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW telemetry_10s
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('10 seconds', time) AS bucket,
    link_id,
    AVG(latency_ms)  AS avg_latency,
    STDDEV(latency_ms) AS std_latency,
    AVG(jitter_ms)   AS avg_jitter,
    MAX(jitter_ms)   AS max_jitter,
    AVG(packet_loss_pct) AS avg_packet_loss,
    MAX(packet_loss_pct) AS max_packet_loss,
    AVG(bandwidth_util_pct) AS avg_bw_util,
    AVG(rtt_ms)      AS avg_rtt
FROM telemetry
GROUP BY bucket, link_id;

-- Retention: raw 7 days, aggregates 90 days
SELECT add_retention_policy('telemetry', INTERVAL '7 days');
SELECT add_retention_policy('telemetry_10s', INTERVAL '90 days');

-- ═══════════════════════════════════════════════════════════
--  PREDICTED HEALTH SCORES (Req-Func-Sw-3)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE health_scores (
    time                TIMESTAMPTZ NOT NULL,
    link_id             UUID        NOT NULL,
    health_score        FLOAT       NOT NULL,  -- 0.0–100.0
    confidence          FLOAT       NOT NULL,  -- 0.0–1.0
    prediction_window_s INT         NOT NULL   -- 30 or 60
);
SELECT create_hypertable('health_scores', 'time');
CREATE INDEX ON health_scores (link_id, time DESC);

-- ═══════════════════════════════════════════════════════════
--  TAMPER-EVIDENT AUDIT LOG (Req-Func-Sw-18, Req-Qual-Sec-3)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE audit_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type      VARCHAR(50) NOT NULL,  -- STEERING, VALIDATION, POLICY_CHANGE, AUTH
    actor           VARCHAR(100),          -- user id or "SYSTEM"
    link_id         UUID,
    health_score    FLOAT,
    confidence      FLOAT,
    validation_result VARCHAR(10),         -- PASSED, FAILED
    routing_change  JSONB,
    policy_change   JSONB,
    details         TEXT,
    checksum        VARCHAR(64)            -- SHA-256 of row content for tamper evidence
);
CREATE INDEX ON audit_log (event_time DESC);
CREATE INDEX ON audit_log (event_type);

-- ═══════════════════════════════════════════════════════════
--  USERS & RBAC (Req-Func-Sw-15, Req-Func-Sw-16)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL,  -- NETWORK_ADMIN, IT_MANAGER, MSP_TECH, IT_STAFF, END_USER
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    failed_attempts INT          NOT NULL DEFAULT 0,
    locked_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════
--  NETWORK POLICIES (Req-Func-Sw-11, Req-Func-Sw-12)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE policies (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    natural_language TEXT        NOT NULL,
    yang_config     JSONB        NOT NULL,
    created_by      UUID         REFERENCES users(id),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ═══════════════════════════════════════════════════════════
--  OPERATIONAL TABLES (steering, sandbox, active policies)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE steering_audit (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action          TEXT NOT NULL,
    source_link     TEXT NOT NULL,
    target_link     TEXT NOT NULL,
    traffic_classes TEXT[],
    confidence      DOUBLE PRECISION,
    reason          TEXT,
    sandbox_validated BOOLEAN,
    status          TEXT NOT NULL
);

CREATE TABLE active_policies (
    name            TEXT PRIMARY KEY,
    traffic_class   TEXT NOT NULL,
    priority        INTEGER NOT NULL,
    bandwidth_guarantee_mbps DOUBLE PRECISION,
    latency_max_ms  DOUBLE PRECISION,
    action          TEXT NOT NULL,
    target_links    TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sandbox_reports (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    result          TEXT NOT NULL,
    details         TEXT,
    loop_free       BOOLEAN NOT NULL,
    policy_compliant BOOLEAN NOT NULL,
    reachability_verified BOOLEAN NOT NULL,
    execution_time_ms DOUBLE PRECISION,
    topology_snapshot JSONB
);
