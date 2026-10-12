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
- Objective: Create a trustworthy, auditable, immutable ledger for stock-direction predictions.
- Files to create/update:
  - `db/migrations/007_ledger.sql`
  - `ml/features.py`
  - `ml/models/naive_last.py`
  - `ml/models/drift.py`
  - `ml/predict.py`
  - `tests/integration/test_phase3.py`
  - `VERSION` -> 0.4.0
- Gate 3 Acceptance:
  - Migration 007 applied idempotently.
  - Valid prediction insertion passes.
  - Invalid prediction rejection (target date <= prediction date, close outside bounds).
  - Horizon check (1, 5, 21 only) and probability_up [0, 1] enforced.
  - UPDATE forbidden trigger blocks updates.
  - DELETE forbidden trigger blocks deletes.
  - TRUNCATE forbidden by role revocation.
  - Baseline predictions generated and verified readable from PostgreSQL.
- Status: IN PROGRESS
