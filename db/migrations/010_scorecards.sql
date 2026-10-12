-- Migration 010: Model Scorecard Materialized View

DROP MATERIALIZED VIEW IF EXISTS mv_model_scorecard CASCADE;

CREATE MATERIALIZED VIEW mv_model_scorecard AS
WITH model_stats AS (
    SELECT 
        p.model_id,
        p.version_id,
        p.ticker_id,
        p.horizon_days,
        COUNT(po.outcome_id) AS sample_size,
        ROUND(AVG(CASE WHEN po.direction_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS direction_accuracy,
        ROUND(AVG(po.absolute_error)::numeric, 4) AS mae,
        ROUND(SQRT(AVG(po.squared_error))::numeric, 4) AS rmse,
        ROUND(AVG(po.log_loss)::numeric, 4) AS mean_log_loss,
        ROUND(AVG(CASE WHEN po.inside_interval THEN 1.0 ELSE 0.0 END)::numeric, 4) AS interval_coverage
    FROM prediction p
    JOIN prediction_outcome po ON p.prediction_id = po.prediction_id
    GROUP BY p.model_id, p.version_id, p.ticker_id, p.horizon_days
),
baseline_stats AS (
    SELECT 
        p.ticker_id,
        p.horizon_days,
        p.target_date,
        po.direction_correct AS baseline_dir_correct
    FROM prediction p
    JOIN model m ON p.model_id = m.model_id
    JOIN prediction_outcome po ON p.prediction_id = po.prediction_id
    WHERE m.name = 'naive_last'
),
paired_baseline AS (
    SELECT 
        p.model_id,
        p.version_id,
        p.ticker_id,
        p.horizon_days,
        ROUND(AVG(CASE WHEN bs.baseline_dir_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS baseline_direction_accuracy
    FROM prediction p
    JOIN prediction_outcome po ON p.prediction_id = po.prediction_id
    JOIN baseline_stats bs ON p.ticker_id = bs.ticker_id 
                          AND p.horizon_days = bs.horizon_days 
                          AND p.target_date = bs.target_date
    GROUP BY p.model_id, p.version_id, p.ticker_id, p.horizon_days
)
SELECT 
    ms.model_id,
    ms.version_id,
    ms.ticker_id,
    ms.horizon_days,
    ms.sample_size,
    ms.direction_accuracy,
    ms.mae,
    ms.rmse,
    ms.mean_log_loss,
    ms.interval_coverage,
    COALESCE(pb.baseline_direction_accuracy, ms.direction_accuracy) AS baseline_direction_accuracy,
    ROUND((ms.direction_accuracy - COALESCE(pb.baseline_direction_accuracy, ms.direction_accuracy))::numeric, 4) AS skill_score,
    (ms.sample_size >= 30) AS is_reliable,
    CASE 
        WHEN ms.sample_size < 30 THEN 
            'Insufficient sample size (n=' || ms.sample_size || ' < 30)'
        WHEN ms.direction_accuracy > COALESCE(pb.baseline_direction_accuracy, 0.0) THEN 
            'Beats baseline with ' || (ms.direction_accuracy * 100)::numeric(5,2) || '% direction accuracy over ' || ms.sample_size || ' samples'
        ELSE 
            'Does not beat naive_last baseline (' || (ms.direction_accuracy * 100)::numeric(5,2) || '% vs ' || (COALESCE(pb.baseline_direction_accuracy, 0.0) * 100)::numeric(5,2) || '%)'
    END AS verdict
FROM model_stats ms
LEFT JOIN paired_baseline pb ON ms.model_id = pb.model_id 
                             AND ms.version_id = pb.version_id 
                             AND ms.ticker_id = pb.ticker_id 
                             AND ms.horizon_days = pb.horizon_days;

-- Create Unique Index for CONCURRENTLY refresh support
CREATE UNIQUE INDEX idx_mv_model_scorecard_pk 
ON mv_model_scorecard (model_id, version_id, ticker_id, horizon_days);

-- Grant SELECT permissions
GRANT SELECT ON mv_model_scorecard TO app_rw, app_ro;
