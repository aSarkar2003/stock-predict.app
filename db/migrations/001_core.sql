-- Migration 001: Core Schema & Stock Price Partitioning

-- Enum for application user roles
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'app_role') THEN
        CREATE TYPE app_role AS ENUM ('viewer', 'analyst', 'admin');
    END IF;
END $$;

-- Table: app_user
CREATE TABLE IF NOT EXISTS app_user (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role app_role NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table: industry
CREATE TABLE IF NOT EXISTS industry (
    industry_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Table: stock_ticker
CREATE TABLE IF NOT EXISTS stock_ticker (
    ticker_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL DEFAULT 'NSE',
    name VARCHAR(255) NOT NULL,
    industry_id INT REFERENCES industry(industry_id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_symbol_exchange UNIQUE (symbol, exchange)
);

-- Table: trading_calendar
CREATE TABLE IF NOT EXISTS trading_calendar (
    calendar_date DATE PRIMARY KEY,
    is_trading_day BOOLEAN NOT NULL DEFAULT TRUE,
    market_open TIMESTAMPTZ,
    market_close TIMESTAMPTZ,
    notes TEXT
);

-- Table: corporate_action
CREATE TABLE IF NOT EXISTS corporate_action (
    action_id BIGSERIAL PRIMARY KEY,
    ticker_id INT NOT NULL REFERENCES stock_ticker(ticker_id) ON DELETE RESTRICT,
    ex_date DATE NOT NULL,
    action_type VARCHAR(20) NOT NULL CHECK (action_type IN ('SPLIT', 'DIVIDEND', 'BONUS')),
    ratio NUMERIC(12, 6),
    amount NUMERIC(14, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_split_ratio CHECK (action_type != 'SPLIT' OR (ratio IS NOT NULL AND ratio > 0))
);

-- Table: ingestion_run (placed before stock_price for foreign key reference)
CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id BIGSERIAL PRIMARY KEY,
    ticker_id INT NOT NULL REFERENCES stock_ticker(ticker_id) ON DELETE RESTRICT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL')),
    records_ingested INT NOT NULL DEFAULT 0,
    records_rejected INT NOT NULL DEFAULT 0,
    error_message TEXT
);

-- Table: stock_price (Partitioned by RANGE on price_date)
CREATE TABLE IF NOT EXISTS stock_price (
    ticker_id INT NOT NULL REFERENCES stock_ticker(ticker_id) ON DELETE RESTRICT,
    price_date DATE NOT NULL,
    open_price NUMERIC(14, 4) NOT NULL,
    high_price NUMERIC(14, 4) NOT NULL,
    low_price NUMERIC(14, 4) NOT NULL,
    close_price NUMERIC(14, 4) NOT NULL,
    volume BIGINT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id BIGINT REFERENCES ingestion_run(run_id) ON DELETE RESTRICT,
    PRIMARY KEY (ticker_id, price_date),
    CONSTRAINT chk_stock_price_positive CHECK (
        open_price >= 0 AND high_price >= 0 AND low_price >= 0 AND close_price >= 0
    ),
    CONSTRAINT chk_stock_price_ohlc CHECK (
        high_price >= low_price AND
        high_price >= open_price AND
        high_price >= close_price AND
        low_price <= open_price AND
        low_price <= close_price
    ),
    CONSTRAINT chk_stock_price_volume CHECK (volume >= 0)
) PARTITION BY RANGE (price_date);

-- Yearly partitions for stock_price (2015 to 2028)
CREATE TABLE IF NOT EXISTS stock_price_2015 PARTITION OF stock_price
    FOR VALUES FROM ('2015-01-01') TO ('2016-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2016 PARTITION OF stock_price
    FOR VALUES FROM ('2016-01-01') TO ('2017-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2017 PARTITION OF stock_price
    FOR VALUES FROM ('2017-01-01') TO ('2018-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2018 PARTITION OF stock_price
    FOR VALUES FROM ('2018-01-01') TO ('2019-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2019 PARTITION OF stock_price
    FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2020 PARTITION OF stock_price
    FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2021 PARTITION OF stock_price
    FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2022 PARTITION OF stock_price
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2023 PARTITION OF stock_price
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2024 PARTITION OF stock_price
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2025 PARTITION OF stock_price
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2026 PARTITION OF stock_price
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE TABLE IF NOT EXISTS stock_price_2027 PARTITION OF stock_price
    FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');

CREATE TABLE IF NOT EXISTS stock_price_default PARTITION OF stock_price DEFAULT;
