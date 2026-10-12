# Changelog

All notable changes to STOCK&PREDICT are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
