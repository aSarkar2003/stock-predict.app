-- Migration 005: Ingestion Rejects, Job Queue, and Split Multiplier Function

-- Table: ingestion_reject
CREATE TABLE IF NOT EXISTS ingestion_reject (
    reject_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT REFERENCES ingestion_run(run_id) ON DELETE CASCADE,
    ticker_id INT REFERENCES stock_ticker(ticker_id) ON DELETE RESTRICT,
    price_date DATE,
    raw_payload JSONB NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Enum for job status
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
        CREATE TYPE job_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
    END IF;
END $$;

-- Table: job_queue
CREATE TABLE IF NOT EXISTS job_queue (
    job_id BIGSERIAL PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status job_status NOT NULL DEFAULT 'PENDING',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_job_queue_pending ON job_queue (status, created_at) WHERE status = 'PENDING';

-- Stored Function: fn_split_multiplier
-- Computes cumulative split factor for price adjustment as of a target date
CREATE OR REPLACE FUNCTION fn_split_multiplier(p_ticker_id INT, p_as_of_date DATE)
RETURNS NUMERIC AS $$
DECLARE
    v_multiplier NUMERIC := 1.0;
    r RECORD;
BEGIN
    FOR r IN 
        SELECT ratio 
        FROM corporate_action
        WHERE ticker_id = p_ticker_id
          AND action_type = 'SPLIT'
          AND ex_date > p_as_of_date
          AND ratio IS NOT NULL 
          AND ratio > 0
    LOOP
        v_multiplier := v_multiplier * r.ratio;
    END LOOP;
    
    RETURN COALESCE(v_multiplier, 1.0);
END;
$$ LANGUAGE plpgsql STABLE;

-- Permissions on new objects for app_rw and app_ro
GRANT SELECT, INSERT, UPDATE, DELETE ON ingestion_reject, job_queue TO app_rw;
GRANT USAGE, SELECT ON SEQUENCE ingestion_reject_reject_id_seq, job_queue_job_id_seq TO app_rw;
GRANT SELECT ON ingestion_reject, job_queue TO app_ro;
