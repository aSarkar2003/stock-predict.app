import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime

from app.db import check_db_health, get_ro_connection, get_db_connection
from ingest.pipeline import IngestionPipeline
from ml.predict import generate_and_persist_prediction
from ml.resolve import resolve_predictions_for_ticker
from ml.scorecards import refresh_scorecard_materialized_view, get_model_scorecards
from ml.models.prophet_model import ProphetForecaster, PROPHET_AVAILABLE

st.set_page_config(
    page_title="STOCK&PREDICT",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 STOCK&PREDICT")
st.caption("Quantitative Stock Forecasting & Model Accountability Platform")

# Sidebar navigation
menu = st.sidebar.selectbox(
    "Navigation",
    ["Dashboard", "Stock Explorer", "Predictions Ledger", "Model Scorecards", "Data Ingestion"]
)

# ----------------------------------------------------
# PAGE A: DASHBOARD
# ----------------------------------------------------
if menu == "Dashboard":
    st.subheader("System Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    db_ok = check_db_health()
    col1.metric("Database Status", "ONLINE" if db_ok else "OFFLINE")

    with get_ro_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stock_ticker WHERE is_active = TRUE;")
            active_tickers = cur.fetchone()[0]
            col2.metric("Active Tickers", active_tickers)

            cur.execute("SELECT COUNT(*) FROM stock_price;")
            total_prices = cur.fetchone()[0]
            col3.metric("Stored Price Records", f"{total_prices:,}")

            cur.execute("SELECT COUNT(*) FROM prediction;")
            total_preds = cur.fetchone()[0]
            col4.metric("Sealed Predictions", total_preds)

    st.divider()
    st.markdown("### Latest Market Observations")
    with get_ro_connection() as conn:
        df_latest = pd.read_sql_query("""
            SELECT DISTINCT ON (st.symbol)
                st.symbol, st.name, sp.price_date, sp.open_price, sp.high_price, sp.low_price, sp.close_price, sp.volume
            FROM stock_price sp
            JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
            ORDER BY st.symbol, sp.price_date DESC;
        """, conn)
    if not df_latest.empty:
        st.dataframe(df_latest, use_container_width=True)
    else:
        st.info("No prices ingested yet. Navigate to Data Ingestion to fetch history.")

# ----------------------------------------------------
# PAGE B: STOCK EXPLORER
# ----------------------------------------------------
elif menu == "Stock Explorer":
    st.subheader("Stock Explorer & Price History")
    
    with get_ro_connection() as conn:
        df_tickers = pd.read_sql_query("SELECT symbol, name, exchange FROM stock_ticker ORDER BY symbol;", conn)

    selected_symbol = st.selectbox("Select Ticker", df_tickers["symbol"].tolist())
    ticker_info = df_tickers[df_tickers["symbol"] == selected_symbol].iloc[0]
    st.write(f"**{ticker_info['name']}** ({ticker_info['exchange']}:{ticker_info['symbol']})")

    with get_ro_connection() as conn:
        df_prices = pd.read_sql_query("""
            SELECT price_date, open_price, high_price, low_price, close_price, volume
            FROM stock_price sp
            JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
            WHERE st.symbol = %s
            ORDER BY price_date ASC;
        """, conn, params=(selected_symbol,))

    if not df_prices.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=df_prices["price_date"],
            open=df_prices["open_price"],
            high=df_prices["high_price"],
            low=df_prices["low_price"],
            close=df_prices["close_price"],
            name="OHLC",
        )])
        fig.update_layout(
            title=f"{selected_symbol} Daily OHLC Candlestick Chart",
            yaxis_title="Price (INR)",
            xaxis_title="Date",
            xaxis_rangeslider_visible=False,
            height=500,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_prices.tail(50), use_container_width=True)
    else:
        st.warning(f"No price history available in PostgreSQL for {selected_symbol}.")

# ----------------------------------------------------
# PAGE C: PREDICTIONS LEDGER
# ----------------------------------------------------
elif menu == "Predictions Ledger":
    st.subheader("Immutable Prediction Ledger")
    st.caption("All predictions are write-once, timestamped, and protected against hindsight alteration.")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("#### Generate New Forecast")
        with get_ro_connection() as conn:
            symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()
            models = pd.read_sql_query("SELECT name FROM model ORDER BY name;", conn)["name"].tolist()

        c1, c2, c3 = st.columns(3)
        t_sym = c1.selectbox("Ticker", symbols)
        m_name = c2.selectbox("Model", models)
        h_days = c3.selectbox("Horizon (Trading Days)", [1, 5, 21])

        if st.button("Generate & Seal Prediction"):
            try:
                res = generate_and_persist_prediction(t_sym, m_name, datetime.date.today(), horizon_days=h_days)
                st.success(f"Prediction sealed! ID: {res['prediction_id']} | Direction: {res['predicted_direction']} | Target: {res['target_date']}")
            except Exception as e:
                st.error(f"Prediction failed: {e}")

    with col2:
        st.markdown("#### Resolution Actions")
        if st.button("Resolve Pending Predictions"):
            count = resolve_predictions_for_ticker()
            st.info(f"Resolved {count} pending predictions.")

    st.divider()
    st.markdown("### 📊 Multi-Model & Ensemble Prediction Visualizer")
    col_chart_sym, col_chart_h = st.columns(2)
    chart_symbol = col_chart_sym.selectbox("Compare Forecasts For Symbol", symbols, key="compare_sym")
    chart_horizon = col_chart_h.selectbox("Forecast Horizon", [1, 5, 21], key="compare_h")

    if st.button("Generate Multi-Model Comparison Chart"):
        with st.spinner("Evaluating models (ANN, LSTM, Transformer, Prophet, Ensemble)..."):
            from ml.models.ensemble_model import EnsembleModel
            with get_ro_connection() as conn:
                df_hist = pd.read_sql_query("""
                    SELECT price_date, close_price FROM stock_price sp
                    JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
                    WHERE st.symbol = %s ORDER BY price_date ASC;
                """, conn, params=(chart_symbol,))

            if len(df_hist) >= 30:
                ens = EnsembleModel()
                all_preds = ens.predict_all(df_hist, horizon_days=chart_horizon)
                ens_pred = ens.predict(df_hist, horizon_days=chart_horizon)
                all_preds["ensemble"] = ens_pred

                last_date = df_hist.iloc[-1]["price_date"]
                last_price = float(df_hist.iloc[-1]["close_price"])

                # Create comparison figure
                comp_fig = go.Figure()
                # Recent history line
                comp_fig.add_trace(go.Scatter(
                    x=df_hist["price_date"].tail(30),
                    y=df_hist["close_price"].tail(30),
                    mode="lines+markers",
                    name="Recent Observed Close",
                    line=dict(color="#1f77b4", width=3),
                ))

                colors = {
                    "naive_last": "#7f7f7f",
                    "drift": "#bcbd22",
                    "ann": "#ff7f0e",
                    "lstm": "#2ca02c",
                    "transformer": "#9467bd",
                    "ensemble": "#d62728",
                }

                # Add each model forecast
                proj_x = [last_date, last_date + datetime.timedelta(days=chart_horizon * 2)]
                for m_k, p_res in all_preds.items():
                    c = colors.get(m_k, "#17becf")
                    w = 4 if m_k == "ensemble" else 2
                    comp_fig.add_trace(go.Scatter(
                        x=proj_x,
                        y=[last_price, p_res["predicted_close"]],
                        mode="lines+markers",
                        name=f"{m_k.upper()} ({p_res['predicted_direction']}: ₹{p_res['predicted_close']})",
                        line=dict(color=c, width=w, dash="solid" if m_k == "ensemble" else "dot"),
                    ))

                # Add Ensemble Confidence Interval Band
                comp_fig.add_trace(go.Scatter(
                    x=[proj_x[1], proj_x[1]],
                    y=[ens_pred["lower_bound"], ens_pred["upper_bound"]],
                    mode="lines",
                    name="Ensemble Bounds [Lower, Upper]",
                    line=dict(color="rgba(214, 39, 40, 0.5)", width=6),
                ))

                comp_fig.update_layout(
                    title=f"{chart_symbol} — Multi-Model & Ensemble Direction Projections (Horizon: {chart_horizon}d)",
                    yaxis_title="Price (INR)",
                    xaxis_title="Timeline",
                    hovermode="x unified",
                    height=500,
                )
                st.plotly_chart(comp_fig, use_container_width=True)

                # Summary metrics table
                summary_data = []
                for m_k, p_res in all_preds.items():
                    summary_data.append({
                        "Model": m_k.upper(),
                        "Predicted Close": f"₹{p_res['predicted_close']:.2f}",
                        "Expected Return": f"{p_res['predicted_log_return'] * 100:.3f}%",
                        "Direction": p_res["predicted_direction"],
                        "Probability UP": f"{p_res['probability_up'] * 100:.1f}%",
                        "Interval [Lower - Upper]": f"₹{p_res['lower_bound']:.2f} - ₹{p_res['upper_bound']:.2f}",
                    })
                st.table(pd.DataFrame(summary_data))
            else:
                st.warning(f"Insufficient history for {chart_symbol} to fit deep learning models.")

    st.divider()
    st.markdown("### Ledger Records")
    with get_ro_connection() as conn:
        df_ledger = pd.read_sql_query("""
            SELECT 
                p.prediction_id,
                st.symbol,
                m.name AS model_name,
                p.prediction_date,
                p.target_date,
                p.horizon_days,
                p.predicted_direction,
                p.predicted_close,
                p.lower_bound,
                p.upper_bound,
                po.actual_close,
                po.direction_correct,
                CASE WHEN po.outcome_id IS NOT NULL THEN 'RESOLVED' ELSE 'PENDING' END AS status
            FROM prediction p
            JOIN stock_ticker st ON p.ticker_id = st.ticker_id
            JOIN model m ON p.model_id = m.model_id
            LEFT JOIN prediction_outcome po ON p.prediction_id = po.prediction_id
            ORDER BY p.prediction_id DESC
            LIMIT 100;
        """, conn)

    if not df_ledger.empty:
        st.dataframe(df_ledger, use_container_width=True)
    else:
        st.info("Ledger is currently empty.")

# ----------------------------------------------------
# PAGE D: MODEL SCORECARDS
# ----------------------------------------------------
elif menu == "Model Scorecards":
    st.subheader("Model Accountability Scorecards")
    st.caption("Rigorous performance metrics evaluated on identical sample periods against naive baselines.")

    if st.button("Refresh Scorecards"):
        refresh_scorecard_materialized_view()
        st.success("Materialized view refreshed!")

    scorecards = get_model_scorecards()
    if scorecards:
        df_scorecards = pd.DataFrame(scorecards)
        st.dataframe(df_scorecards, use_container_width=True)
    else:
        st.info("No resolved prediction scorecards available yet.")

# ----------------------------------------------------
# PAGE E: DATA INGESTION
# ----------------------------------------------------
elif menu == "Data Ingestion":
    st.subheader("Market Data Ingestion")
    
    with get_ro_connection() as conn:
        symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()

    t_choice = st.selectbox("Select Symbol to Ingest", symbols)
    c1, c2 = st.columns(2)
    s_date = c1.date_input("Start Date", datetime.date(2023, 1, 1))
    e_date = c2.date_input("End Date", datetime.date.today())

    if st.button("Trigger Ingestion"):
        with st.spinner("Ingesting from Yahoo Finance..."):
            pipeline = IngestionPipeline()
            try:
                res = pipeline.run_for_ticker(t_choice, s_date, e_date)
                st.success(f"Ingestion {res['status']}: {res['ingested']} rows ingested, {res['rejected']} rows rejected.")
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

    st.divider()
    st.markdown("### Recent Ingestion Runs")
    with get_ro_connection() as conn:
        df_runs = pd.read_sql_query("""
            SELECT ir.run_id, st.symbol, ir.status, ir.records_ingested, ir.records_rejected, ir.started_at, ir.completed_at
            FROM ingestion_run ir
            JOIN stock_ticker st ON ir.ticker_id = st.ticker_id
            ORDER BY ir.run_id DESC LIMIT 20;
        """, conn)
    st.dataframe(df_runs, use_container_width=True)
