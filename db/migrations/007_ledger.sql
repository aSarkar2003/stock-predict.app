-- Migration 007: Append-Only Prediction Ledger

-- Table: prediction
CREATE TABLE IF NOT EXISTS prediction (
    prediction_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    ticker_id INT NOT NULL REFERENCES stock_ticker(ticker_id) ON DELETE RESTRICT,
    model_id INT NOT NULL REFERENCES model(model_id) ON DELETE RESTRICT,
    version_id INT NOT NULL REFERENCES model_version(version_id) ON DELETE RESTRICT,
    prediction_date DATE NOT NULL,
    target_date DATE NOT NULL,
    horizon_days INT NOT NULL CHECK (horizon_days IN (1, 5, 21)),
    predicted_log_return NUMERIC(12, 6) NOT NULL,
    predicted_close NUMERIC(14, 4) NOT NULL,
    lower_bound NUMERIC(14, 4) NOT NULL,
    upper_bound NUMERIC(14, 4) NOT NULL,
    probability_up NUMERIC(5, 4) NOT NULL CHECK (probability_up >= 0.0 AND probability_up <= 1.0),
    predicted_direction VARCHAR(10) NOT NULL DEFAULT 'UP' CHECK (predicted_direction IN ('UP', 'DOWN', 'FLAT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Validation Trigger Function
CREATE OR REPLACE FUNCTION fn_validate_prediction()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.target_date <= NEW.prediction_date THEN
        RAISE EXCEPTION 'target_date (%) must be strictly after prediction_date (%)', NEW.target_date, NEW.prediction_date;
    END IF;

    IF NEW.lower_bound > NEW.predicted_close OR NEW.predicted_close > NEW.upper_bound THEN
        RAISE EXCEPTION 'predicted_close (%) must lie within lower_bound (%) and upper_bound (%)', 
            NEW.predicted_close, NEW.lower_bound, NEW.upper_bound;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_validate_prediction ON prediction;
CREATE TRIGGER tg_validate_prediction
    BEFORE INSERT ON prediction
    FOR EACH ROW
    EXECUTE FUNCTION fn_validate_prediction();

-- Mutation Blocking Function (Append-Only Enforcement)
CREATE OR REPLACE FUNCTION fn_forbid_prediction_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'prediction table is append-only: UPDATE and DELETE operations are forbidden';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_forbid_prediction_mutation ON prediction;
CREATE TRIGGER tg_forbid_prediction_mutation
    BEFORE UPDATE OR DELETE ON prediction
    FOR EACH ROW
    EXECUTE FUNCTION fn_forbid_prediction_mutation();

-- Grants and Revokes
GRANT SELECT, INSERT ON prediction TO app_rw;
GRANT USAGE, SELECT ON SEQUENCE prediction_prediction_id_seq TO app_rw;
GRANT SELECT ON prediction TO app_ro;

REVOKE UPDATE, DELETE, TRUNCATE ON prediction FROM app_rw, app_ro, PUBLIC;
