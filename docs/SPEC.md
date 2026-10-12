# SPECIFICATION: STOCK&PREDICT

## 1. Overview
STOCK&PREDICT is an institutional-grade stock direction prediction and model accountability platform.
Every prediction made by any model (baseline or ML) is written to an immutable append-only ledger, preventing hindsight tampering.
Real market observations subsequently grade predictions automatically, calculating directional accuracy, MAE, RMSE, and skill scores against a standard "tomorrow = today" naive baseline.

## 2. Architecture & Design Principles
- PostgreSQL 16 is the single source of truth.
- Append-only prediction ledger enforced with database triggers and `REVOKE` privileges.
- Partitioning: `stock_price` partitioned by year (2015–2028).
- Role-based separation: `app_owner` owns schema and runs migrations; `app_rw` has DML access; `app_ro` has read-only access.
- Idempotent ingestion pipeline with job queues and reject tracking.
- Independent verification: pandas recalculations cross-check SQL materialized views.

## 3. Supported Markets & Instruments
- Indian Equities listed on the National Stock Exchange (NSE) and Bombay Stock Exchange (BSE).
- Yahoo Finance symbols with `.NS` and `.BO` extensions (e.g. `RELIANCE.NS`, `TCS.NS`, `INFY.NS`).
- Standard OHLCV observations adjusted for stock splits using corporate action multipliers.

## 4. Database Schema Specification

### 4.1 Prediction Ledger
- Table: `prediction`
- Columns: `prediction_id`, `user_id`, `ticker_id`, `model_id`, `version_id`, `prediction_date`, `target_date`, `horizon_days`, `predicted_log_return`, `predicted_close`, `lower_bound`, `upper_bound`, `probability_up`, `created_at`.
- Validation trigger `tg_validate_prediction`: Enforces `target_date > prediction_date`, `lower_bound <= predicted_close <= upper_bound`.
- Immutability trigger `tg_forbid_prediction_mutation`: Prohibits `UPDATE` and `DELETE`.
- Permissions: `REVOKE UPDATE, DELETE, TRUNCATE ON prediction FROM app_rw, app_ro, PUBLIC;`

### 4.2 Outcome Resolution
- Table: `prediction_outcome`
- Columns: `outcome_id`, `prediction_id`, `actual_close`, `actual_log_return`, `direction_correct`, `log_loss`, `absolute_error`, `squared_error`, `inside_interval`, `resolved_at`.
- Function: `fn_resolve_predictions(p_ticker_id INT DEFAULT NULL)`: Resolves predictions whose target date prices have been ingested.
- Trigger `tg_run_done_auto_resolve`: Fires after successful ingestion runs.

### 4.3 Model Scorecards
- Materialized View: `mv_model_scorecard`
- Computes sample size, directional accuracy, MAE, RMSE, mean log loss, interval coverage, paired baseline accuracy, skill score, and human-readable verdict.
- Unique Index: `idx_mv_model_scorecard_pk` on `(model_id, version_id, ticker_id, horizon_days)` enabling concurrent refresh.

### 4.4 Ingestion Pipeline
- Table: `ingestion_run`
- Table: `ingestion_reject`
- Table: `job_queue` with status enum `('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')`.
- Function: `fn_split_multiplier(p_ticker_id INT, p_as_of_date DATE)` returns cumulative split adjustment factor.

### 4.6 Core Schema
- `app_user`: System users with hashed passwords and roles (`viewer`, `analyst`, `admin`).
- `industry`: Industry classification.
- `stock_ticker`: Equities with exchange and active flags.
- `trading_calendar`: Exchange trading days (2015–2027) distinguishing trading sessions from weekends and holidays.
- `corporate_action`: Stock splits, dividends, bonuses.
- `stock_price`: Range-partitioned by `price_date` with OHLC and non-negative volume constraints.
- `model`: Model catalog (`naive_last`, `drift`, Prophet, etc.).
- `model_version`: Tagged model versions with hyperparameters.
- `backtest_result`: Backtest evaluations.
