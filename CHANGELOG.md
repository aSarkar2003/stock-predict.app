# Changelog

All notable changes to STOCK&PREDICT are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
