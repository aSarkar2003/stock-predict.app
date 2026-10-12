-- Migration 002: Model Registry Tables

-- Table: model
CREATE TABLE IF NOT EXISTS model (
    model_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_baseline BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table: model_version
CREATE TABLE IF NOT EXISTS model_version (
    version_id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES model(model_id) ON DELETE RESTRICT,
    version_tag VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_model_version UNIQUE (model_id, version_tag)
);

-- Table: backtest_result
CREATE TABLE IF NOT EXISTS backtest_result (
    backtest_id BIGSERIAL PRIMARY KEY,
    version_id INT NOT NULL REFERENCES model_version(version_id) ON DELETE RESTRICT,
    ticker_id INT NOT NULL REFERENCES stock_ticker(ticker_id) ON DELETE RESTRICT,
    horizon_days INT NOT NULL CHECK (horizon_days IN (1, 5, 21)),
    metric_name VARCHAR(50) NOT NULL,
    metric_value NUMERIC(14, 6) NOT NULL,
    sample_size INT NOT NULL CHECK (sample_size > 0),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

