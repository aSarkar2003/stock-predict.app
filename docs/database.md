# Database Documentation: STOCK&PREDICT

## Entity Relationship Overview
The database design models financial time-series observations, market corporate actions, forecasting models, and performance tracking.

### Tables
1. **app_user**: Stores administrative and analytical users with Argon2 password hashes.
2. **industry**: Normalized industry categories.
3. **stock_ticker**: Equity identifiers (`symbol`, `exchange`, `name`, `industry_id`).
4. **trading_calendar**: Date-level trading session indicators for NSE/BSE holidays and weekends.
5. **corporate_action**: Splits, bonuses, dividends with associated adjustment ratios.
6. **ingestion_run**: Metadata on batch ingestion jobs (success, fail, count).
7. **stock_price**: Partitioned range table (by year, 2015–2028). Holds daily OHLCV values.
8. **model**: Catalog of forecasting algorithms.
9. **model_version**: Specific deployed hyperparameters and versions.
10. **backtest_result**: Historical walk-forward backtest results.
11. **ingestion_reject**: Log of unparseable or constraint-violating input records.
12. **job_queue**: FIFO transactional job queue using `FOR UPDATE SKIP LOCKED`.
13. **prediction**: Immutable append-only forecasts.
14. **prediction_outcome**: Graded realizations with logarithmic and quadratic losses.

### Materialized Views
- **mv_model_scorecard**: Aggregated statistical metrics per model, version, ticker, and horizon.
