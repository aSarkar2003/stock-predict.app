"""
Execution progress log for STOCK&PREDICT phases.
"""
# Phase Execution Log

## Phase 0: Infrastructure and Bootstrap
- Status: COMPLETED
- Tag: `v0.1.0` (commit `6e37f0e`)
- Tests: 3 passed

## Phase 1: Core Schema and Seeds
- Status: COMPLETED
- Tag: `v0.2.0` (commit `6d72727`)
- Tests: 10 passed

## Phase 2: Historical Stock-Data Ingestion
- Status: COMPLETED
- Tag: `v0.3.0` (commit `e4101e7`)
- Tests: 16 passed

## Phase 3: Immutable Prediction Ledger
- Status: COMPLETED
- Tag: `v0.4.0` (commit `c081242`)
- Tests: 23 passed

## Phase 4: Outcome Resolution and Model Scorecards
- Objective: Resolve historical predictions against actual observations, calculate scorecards, cross-check metrics against pandas, integrate Prophet experimental model, and provide interactive Streamlit dashboard.
- Files to create/update:
  - `db/migrations/009_resolution.sql` (`prediction_outcome`, `fn_resolve_predictions`, `tg_run_done_auto_resolve`, `v_pending_predictions`)
  - `db/migrations/010_scorecards.sql` (`mv_model_scorecard`, unique index, grants)
  - `ml/resolve.py`
  - `ml/scorecards.py`
  - `ml/models/prophet_model.py`
  - `docs/ml_methodology.md`
  - `streamlit_app.py`
  - `tests/integration/test_phase4.py`
  - `VERSION` -> 0.5.0
- Gate 4 Acceptance:
  - Migrations 009 and 010 applied cleanly.
  - Correct resolution of predictions into `prediction_outcome`.
  - Idempotent resolution and immutability of outcomes.
  - Auto-resolution trigger on ingestion completion.
  - Scorecard materialized view refresh and unique index.
  - Independent pandas calculation agrees with SQL metrics within tolerance.
  - Prophet model fitting on historical observations without leakage.
  - Streamlit dashboard connected to database.
- Status: IN PROGRESS
