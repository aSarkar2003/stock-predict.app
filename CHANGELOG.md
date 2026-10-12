# Changelog

All notable changes to STOCK&PREDICT are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-12

[![Version](https://img.shields.io/badge/version-0.4.0-blue)](https://github.com/atanu-sarkar/stock-predict-app/releases/tag/v0.4.0)
[![Phase](https://img.shields.io/badge/phase-3-brightgreen)](https://github.com/atanu-sarkar/stock-predict-app)

### Added
- Phase 3: Immutable Prediction Ledger.
- Database migration `007_ledger.sql`:
  - `prediction` table supporting multi-ticker, multi-model forecasts with horizons 1, 5, and 21 trading days.
  - Direction classification (`UP`, `DOWN`, `FLAT`) and prediction intervals (`lower_bound`, `upper_bound`, `probability_up`).
  - Validation trigger `tg_validate_prediction`: Enforces strictly forward target dates (`target_date > prediction_date`) and bounds inclusion (`lower_bound <= predicted_close <= upper_bound`).
  - Immutability trigger `tg_forbid_prediction_mutation`: Completely forbids `UPDATE` and `DELETE` operations.
  - Role-level `REVOKE UPDATE, DELETE, TRUNCATE` on prediction table from `app_rw`, `app_ro`, and `PUBLIC`.
- Feature engineering and baseline models:
  - `ml/features.py`: Computes logarithmic returns and classifies directional labels (`UP`, `DOWN`, `FLAT`).
  - `ml/models/naive_last.py`: Implements "tomorrow = today" random-walk baseline model.
  - `ml/models/drift.py`: Implements linear drift model with volatility bands.
  - `ml/predict.py`: End-to-end prediction generation ensuring zero look-ahead data leakage by strictly evaluating data prior to `as_of_date`.
- Comprehensive test suite in `tests/integration/test_phase3.py` verifying all 7 acceptance checks.

### Validation
- Valid predictions inserted and verified in PostgreSQL.
- Invalid predictions rejected (past dates, invalid intervals, out-of-bounds prices).
- Attempted mutations (`UPDATE`, `DELETE`, `TRUNCATE`) proven rejected by database engine.
- Baseline models executed and written to ledger without hindsight bias.
- 23 passed tests across test suite.

### Git
- Release tag: `v0.4.0`

## [0.3.0] - 2026-10-12

[![Version](https://img.shields.io/badge/version-0.3.0-blue)](https://github.com/atanu-sarkar/stock-predict-app/releases/tag/v0.3.0)
[![Phase](https://img.shields.io/badge/phase-2-brightgreen)](https://github.com/atanu-sarkar/stock-predict-app)

### Added
- Phase 2: Historical Stock-Data Ingestion.
- Database migration `005_ingestion_queue.sql`:
  - `ingestion_reject` table for tracking rejected/malformed rows with failure rationale.
  - `job_queue` table with status tracking (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
  - Stored function `fn_split_multiplier(ticker_id, as_of_date)` for cumulative stock split adjustment.
- Data ingestion layer:
  - `ingest/providers/base.py`: Abstract provider interface.
  - `ingest/providers/yfinance_provider.py`: Yahoo Finance provider supporting NSE (`.NS`) and BSE (`.BO`) tickers.
  - `ingest/validate.py`: Robust OHLC ordering and non-negative volume validation.
  - `ingest/pipeline.py`: Transactional ingestion with automatic upsert into partitioned `stock_price` and reject recording.
  - `ingest/worker.py`: Background job worker with concurrency safety using PostgreSQL `FOR UPDATE SKIP LOCKED`.
  - `ingest/backfill.py`: Resumable backfill utility.
- Integration tests in `tests/integration/test_phase2.py`:
  - Validation rules for negative values and OHLC consistency.
  - Ingestion idempotency.
  - Rejection logging.
  - Cumulative split factor calculation.
  - Atomic job queue claiming and processing.

### Validation
- Ingestion idempotency verified (re-ingesting identical dates causes zero duplicates).
- Split-multiplier function verified.
- Initial backfill executed against Yahoo Finance for NSE equities.
- 16 passed tests across full test suite.

### Git
- Release tag: `v0.3.0`

## [0.2.0] - 2026-10-12

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](https://github.com/atanu-sarkar/stock-predict-app/releases/tag/v0.2.0)
[![Phase](https://img.shields.io/badge/phase-1-brightgreen)](https://github.com/atanu-sarkar/stock-predict-app)

### Added
- Phase 1: Core Schema and Seeds.
- Core schema migrations:
  - `001_core.sql`: `app_role`, `app_user`, `industry`, `stock_ticker`, `trading_calendar`, `corporate_action`, `ingestion_run`, and `stock_price` partitioned by year (2015 to 2028).
  - `002_model.sql`: `model`, `model_version`, and `backtest_result`.
  - `008_grants.sql`: Principle of least privilege role permissions and default privileges for `app_rw` and `app_ro`.
- Comprehensive database seeder `db/seed.py`:
  - 3 system users with Argon2 password hashing (`admin_user`, `analyst_user`, `viewer_user`).
  - 10 Indian equity tickers across major sectors (`RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `ICICIBANK`, `KOTAKBANK`, `LT`, `ITC`, `SBIN`, `BHARTIARTL`).
  - Full exchange trading calendar from 2015 to 2027 with NSE official holidays distinguished from trading sessions.
  - Baseline forecasting models `naive_last` and `drift` with initial version metadata.
- Authoritative documentation in `docs/SPEC.md`, `docs/PRD.md`, and `docs/database.md`.
- Database constraint and permission acceptance test suite `tests/integration/test_phase1.py`.

### Validation
- All migrations applied cleanly to a fresh database and verified repeatable with zero schema drift.
- Verified `stock_price` range partitioning and presence of all yearly child tables.
- Database constraints verified: OHLC price ordering checks, non-negative volume, split ratio positivity, and natural key uniqueness.
- Role enforcement verified: `app_rw` writes successfully, while `app_ro` is prevented from table mutations.
- 10 passed tests across unit and integration test suites.

### Git
- Release tag: `v0.2.0`

## [0.1.0] - 2026-10-12

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](https://github.com/atanu-sarkar/stock-predict-app/releases/tag/v0.1.0)
[![Phase](https://img.shields.io/badge/phase-0-brightgreen)](https://github.com/atanu-sarkar/stock-predict-app)

### Added
- Phase 0: Infrastructure and Bootstrap.
- Python 3.11 virtual environment and dependency configuration (`requirements.txt`, `requirements-dev.txt`).
- Docker Compose configuration for PostgreSQL 16 (`docker-compose.yml`, persistent volume `stock_predict_pgdata`, healthcheck).
- Role initialization scripts (`db/init/000_roles.sh`, `db/init_roles.py`) defining `app_owner`, `app_rw`, `app_ro`.
- Migration runner `db/migrate.py` with idempotent tracking in `schema_migrations`.
- Connection pooling and lifecycle management in `app/db.py` using `psycopg 3` (`psycopg_pool`).
- FastAPI application in `app/main.py` with `/health` verifying PostgreSQL connectivity (`{"db": "ok"}`).
- Initial unit test suite in `tests/unit/test_phase0.py`.
- Automated CI workflow in `.github/workflows/tests.yml`.

### Validation
- Installed all dependencies including `fastapi`, `uvicorn`, `psycopg`, `prophet`, `pandas`, `scikit-learn`, `streamlit`.
- Database role initialization executed cleanly.
- `python db/migrate.py` executed idempotently.
- `/health` endpoint verified returning `{"db": "ok"}`.
- Verified connecting as `app_rw` yields `app_rw` role.
- Verified database failure safeguard in test suite.
- All Phase 0 unit tests passed.

### Git
- Release tag: `v0.1.0`
