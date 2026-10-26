# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Quantitative research analysts, financial ML practitioners, and institutional evaluators benchmarking predictive equity models on Indian market data (NSE & BSE). They evaluate model performance under strict reproducibility conditions and need clear distinction between theoretical backtesting and forward live execution feasibility.

## Product Purpose

STOCK&PREDICT provides an institutional-grade, verifiable framework for Indian equity direction forecasting, time-series projection, and automated prediction resolution. It exists to eliminate look-ahead bias and model overfitting by sealing predictions in an immutable database ledger before future market observations occur, then grading them automatically with statistical scorecards as actual closing prices arrive.

## Positioning

Unlike conventional stock screeners or black-box trading dashboards that report unverified backtests, STOCK&PREDICT enforces database-level immutability (PostgreSQL triggers forbidding `UPDATE` and `DELETE` on predictions) combined with real-time live trading connectivity cues, multi-model consensus ensembling (LSTM, ANN, Transformer, Prophet), and strict zero-leakage cutoff horizons.

## Operating Context

- **Environment**: Local web interface powered by Streamlit and FastAPI with PostgreSQL 16 connection pooling.
- **Data Source**: Daily historical and live OHLCV data from Indian exchanges (NSE/BSE) via yfinance with validation rules (High >= Low, Volume >= 0).
- **Security & Access**: Role-based access control with Argon2-hashed credentials (`Admin` / `admin` demo role) and a partitioned guest market overview.
- **Workflow**: Automated or manual market data ingestion -> Multi-architecture model inference -> Sealed immutable database ledger -> Realized outcome resolution -> Materialized view performance scorecards.

## Capabilities and Constraints

- **Confirmed Capabilities**:
  - Year-based range partitioning in PostgreSQL (2015–2028).
  - Neural network and time-series architectures: Naive Last, Drift, ANN (15 technical features), LSTM (recurrent rolling sequences), Transformer (multi-head temporal self-attention), and Consensus Ensemble with uncertainty confidence bands.
  - Idempotent upserting with rejection logging for bad market ticks.
  - Automated database triggers for prediction validation, immutability, and post-ingestion outcome resolution.
  - Multi-ticker dynamic selection (RELIANCE, TCS, INFY, ITC, HDFCBANK, ICICIBANK, KOTAKBANK, LT, SBIN, BHARTIARTL).
- **Constraints**:
  - PostgreSQL is the sole source of truth; no in-memory or uncommitted local caches.
  - Strictly no modification or deletion of sealed predictions.
  - Streamlit frontend must maintain tight integration with the existing `app/db.py` connection pool and service layer.

## Brand Commitments

- **Product Name**: STOCK&PREDICT
- **Tone**: Analytical, institutional, disciplined, authoritative, high-craft, precision-focused.
- **Visual Identity**: Modern glassmorphic terminal aesthetic with dark slate tones, distinct accent badges for model types, and clear, human-readable statistical callouts.

## Evidence on Hand

- Fully functional PostgreSQL schema with range partitioning (`db/migrations/001_core.sql`, `002_model.sql`).
- Complete test suite passing 28 automated integration tests (`tests/integration/`, `tests/unit/`).
- Realized database observations for 10 core Indian equities backfilled across 2020–2024.
- Deterministic NumPy implementations of neural forecasters (`ml/models/`) and Facebook Prophet integration.

## Product Principles

1. **Uncompromising Truth in Data**: PostgreSQL is the immutable ledger of record. Never fabricate missing dates, hallucinate model results, or allow predictions to be modified after market cutoff.
2. **Zero Look-Ahead Bias**: Every prediction is bound strictly to the observation cutoff date; training and feature calculation must never leak future data into past decisions.
3. **Execution Clarity**: Every forecast must present clear directional probabilities, target price levels, and explicit confidence/uncertainty intervals.
4. **Resilient Idempotency**: Ingestions, evaluations, and migrations must be safe to rerun without corrupting state or creating duplicate records.

## Accessibility & Inclusion

- High contrast text on dark backgrounds conforming to WCAG AA guidelines.
- Standard tabular alternatives for all interactive charts and visual graphs.
- Clear semantic state indicators (colors accompanied by textual tags and status pills).

