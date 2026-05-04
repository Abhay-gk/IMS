-- ═══════════════════════════════════════════════════════════════════
-- IMS PostgreSQL Schema — Source of Truth
-- TimescaleDB extension for time-series aggregations
-- ═══════════════════════════════════════════════════════════════════

-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ─── Work Items (Incident Records) ──────────────────────────────
CREATE TABLE IF NOT EXISTS work_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id    VARCHAR(100) NOT NULL,
    component_type  VARCHAR(50)  NOT NULL,        -- RDBMS, CACHE, API, MCP, QUEUE, NOSQL
    severity        VARCHAR(5)   NOT NULL,         -- P0, P1, P2, P3
    status          VARCHAR(20)  NOT NULL DEFAULT 'OPEN',
    title           TEXT         NOT NULL,
    signal_count    INTEGER      NOT NULL DEFAULT 1,
    first_signal_at TIMESTAMPTZ  NOT NULL,
    last_signal_at  TIMESTAMPTZ  NOT NULL,
    assigned_to     VARCHAR(100),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_status CHECK (status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED')),
    CONSTRAINT chk_severity CHECK (severity IN ('P0', 'P1', 'P2', 'P3'))
);

CREATE INDEX idx_work_items_status ON work_items(status);
CREATE INDEX idx_work_items_severity ON work_items(severity);
CREATE INDEX idx_work_items_component ON work_items(component_id);

-- ─── RCA Records (Root Cause Analysis) ──────────────────────────
CREATE TABLE IF NOT EXISTS rca_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id        UUID UNIQUE NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    incident_start      TIMESTAMPTZ NOT NULL,
    incident_end        TIMESTAMPTZ NOT NULL,
    root_cause_category VARCHAR(50) NOT NULL,
    root_cause_detail   TEXT        NOT NULL,
    fix_applied         TEXT        NOT NULL,
    prevention_steps    TEXT        NOT NULL,
    mttr_seconds        INTEGER     NOT NULL DEFAULT 0,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_rca_category CHECK (root_cause_category IN (
        'Infrastructure', 'Code Bug', 'Configuration',
        'External Dependency', 'Capacity', 'Network', 'Unknown'
    ))
);

-- ─── Signal Metrics (TimescaleDB Hypertable) ────────────────────
CREATE TABLE IF NOT EXISTS signal_metrics (
    time            TIMESTAMPTZ  NOT NULL,
    component_id    VARCHAR(100) NOT NULL,
    component_type  VARCHAR(50)  NOT NULL,
    signal_count    INTEGER      NOT NULL DEFAULT 1,
    avg_latency_ms  DOUBLE PRECISION
);

SELECT create_hypertable('signal_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX idx_signal_metrics_component ON signal_metrics(component_id, time DESC);
