# Product Requirements Document (PRD): STOCK&PREDICT

## 1. Summary
STOCK&PREDICT is a quantitative database platform ensuring accountability for equity forecasting models.
Instead of allowing retrospective model evaluation or selective reporting, all forecasts are timestamped in a write-only ledger, and performance metrics are independently proven against realized market data.

## 2. Core Problem
Forecasting algorithms often present overfitted or unverified backtest figures without audit trails.
Users lack objective verification whether a predictive model systematically outperforms trivial baselines ("tomorrow = today").

## 3. Product Goals
- G1: Append-only immutable prediction storage.
- G2: Automated grading of forecasts upon ingestion of target prices.
- G3: Strict comparison to naive baseline with sample size tracking.
- G4: High-integrity, partitioned market data store with corporate action awareness.
- G5: Clear interactive dashboard for visual inspection of prices, predictions, and scorecards.

## 4. Personas
- **Viewer**: Queries price charts, active tickers, model predictions, and performance scorecards.
- **Analyst**: Generates model forecasts and triggers data ingestion pipelines.
- **Admin**: Manages models, user access, and system operations.

## 5. Scope Phases
- Phase 0: Infrastructure and Bootstrap.
- Phase 1: Core Schema and Seeds (Partitions, Calendar, Tickers, Baselines).
- Phase 2: Ingestion Pipeline (yfinance adapter, validation, reject ledger, split multiplier).
- Phase 3: Immutable Prediction Ledger (triggers, constraints, permissions).
- Phase 4: Resolution Engine and Scorecards (independent pandas cross-validation, Prophet integration).
