-- Migration 009: Outcome Ledger & Auto-Resolution

-- Table: prediction_outcome
CREATE TABLE IF NOT EXISTS prediction_outcome (
    outcome_id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT NOT NULL UNIQUE REFERENCES prediction(prediction_id) ON DELETE RESTRICT,
    actual_close NUMERIC(14, 4) NOT NULL,
    actual_log_return NUMERIC(12, 6) NOT NULL,
    direction_correct BOOLEAN NOT NULL,
    log_loss NUMERIC(12, 6) NOT NULL,
    absolute_error NUMERIC(14, 4) NOT NULL,
    squared_error NUMERIC(16, 6) NOT NULL,
    inside_interval BOOLEAN NOT NULL,
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Immutability Trigger Function
CREATE OR REPLACE FUNCTION fn_forbid_outcome_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'prediction_outcome table is append-only: UPDATE and DELETE operations are forbidden';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_forbid_outcome_mutation ON prediction_outcome;
CREATE TRIGGER tg_forbid_outcome_mutation
    BEFORE UPDATE OR DELETE ON prediction_outcome
    FOR EACH ROW
    EXECUTE FUNCTION fn_forbid_outcome_mutation();

-- Grants and Revokes
GRANT SELECT, INSERT ON prediction_outcome TO app_rw;
GRANT USAGE, SELECT ON SEQUENCE prediction_outcome_outcome_id_seq TO app_rw;
GRANT SELECT ON prediction_outcome TO app_ro;

REVOKE UPDATE, DELETE, TRUNCATE ON prediction_outcome FROM app_rw, app_ro, PUBLIC;

-- View: v_pending_predictions
CREATE OR REPLACE VIEW v_pending_predictions AS
SELECT 
    p.prediction_id,
    p.user_id,
    p.ticker_id,
    p.model_id,
    p.version_id,
    p.prediction_date,
    p.target_date,
    p.horizon_days,
    p.predicted_log_return,
    p.predicted_close,
    p.lower_bound,
    p.upper_bound,
    p.probability_up,
    p.predicted_direction,
    sp_target.close_price AS target_close_price,
    sp_pred.close_price AS pred_close_price
FROM prediction p
JOIN stock_price sp_target ON p.ticker_id = sp_target.ticker_id AND p.target_date = sp_target.price_date
JOIN stock_price sp_pred ON p.ticker_id = sp_pred.ticker_id AND p.prediction_date = sp_pred.price_date
LEFT JOIN prediction_outcome po ON p.prediction_id = po.prediction_id
WHERE po.prediction_id IS NULL;

-- Stored Function: fn_resolve_predictions
CREATE OR REPLACE FUNCTION fn_resolve_predictions(p_ticker_id INT DEFAULT NULL)
RETURNS INT AS $$
DECLARE
    v_resolved_count INT := 0;
    r RECORD;
    v_actual_log_ret NUMERIC(12, 6);
    v_dir_correct BOOLEAN;
    v_log_loss NUMERIC(12, 6);
    v_abs_err NUMERIC(14, 4);
    v_sq_err NUMERIC(16, 6);
    v_in_interval BOOLEAN;
    v_prob NUMERIC(12, 6);
BEGIN
    FOR r IN 
        SELECT * FROM v_pending_predictions
        WHERE (p_ticker_id IS NULL OR ticker_id = p_ticker_id)
    LOOP
        -- Calculate actual log return
        v_actual_log_ret := ROUND(LN(r.target_close_price / r.pred_close_price)::numeric, 6);
        
        -- Direction correctness
        v_dir_correct := (r.predicted_log_return >= 0 AND v_actual_log_ret >= 0) OR
                         (r.predicted_log_return < 0 AND v_actual_log_ret < 0);
        
        -- Log Loss calculation
        v_prob := LEAST(GREATEST(r.probability_up, 0.0001), 0.9999);
        IF v_actual_log_ret >= 0 THEN
            v_log_loss := ROUND((-LN(v_prob))::numeric, 6);
        ELSE
            v_log_loss := ROUND((-LN(1.0 - v_prob))::numeric, 6);
        END IF;

        -- Absolute Error & Squared Error
        v_abs_err := ABS(r.predicted_close - r.target_close_price);
        v_sq_err := (r.predicted_close - r.target_close_price) ^ 2;
        
        -- Interval coverage
        v_in_interval := (r.target_close_price >= r.lower_bound AND r.target_close_price <= r.upper_bound);

        -- Insert outcome
        INSERT INTO prediction_outcome (
            prediction_id, actual_close, actual_log_return, direction_correct,
            log_loss, absolute_error, squared_error, inside_interval
        )
        VALUES (
            r.prediction_id, r.target_close_price, v_actual_log_ret, v_dir_correct,
            v_log_loss, v_abs_err, v_sq_err, v_in_interval
        )
        ON CONFLICT (prediction_id) DO NOTHING;

        v_resolved_count := v_resolved_count + 1;
    END LOOP;

    RETURN v_resolved_count;
END;
$$ LANGUAGE plpgsql;

-- Auto-Resolution Trigger Function after Ingestion Run Completion
CREATE OR REPLACE FUNCTION fn_auto_resolve_on_ingest()
RETURNS TRIGGER AS $$
BEGIN
    IF (NEW.status = 'SUCCESS' OR NEW.status = 'PARTIAL') AND (OLD.status IS NULL OR OLD.status = 'RUNNING') THEN
        PERFORM fn_resolve_predictions(NEW.ticker_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_run_done_auto_resolve ON ingestion_run;
CREATE TRIGGER tg_run_done_auto_resolve
    AFTER UPDATE ON ingestion_run
    FOR EACH ROW
    EXECUTE FUNCTION fn_auto_resolve_on_ingest();
