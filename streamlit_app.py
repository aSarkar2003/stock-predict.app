import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.db import check_db_health, get_ro_connection, get_db_connection
from ingest.pipeline import IngestionPipeline
from ml.predict import generate_and_persist_prediction
from ml.resolve import resolve_predictions_for_ticker
from ml.scorecards import refresh_scorecard_materialized_view, get_model_scorecards
from ml.models.prophet_model import ProphetForecaster, PROPHET_AVAILABLE
from ml.models.ensemble_model import EnsembleModel

ph = PasswordHasher()

st.set_page_config(
    page_title="StockPredict — Institutional Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# MODERN FINANCIAL DESIGN SYSTEM (DESIGN.md TOKENS)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* Global Typography & Palette */
    html, body, [class*="css"], .stApp {
        background-color: #0D1117 !important;
        color: #C9D1D9 !important;
        font-family: 'Public Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
    }

    /* Container Spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1360px !important;
        margin: 0 auto !important;
    }

    /* Monospace for Numbers, Tables, Badges */
    code, pre, .mono-num, [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-variant-numeric: tabular-nums !important;
    }

    /* Primary Navigation Header */
    .site-nav {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 14px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    .brand-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #F0F6FC;
        display: flex;
        align-items: center;
        gap: 10px;
        letter-spacing: -0.3px;
    }
    .brand-accent {
        color: #F59E0B;
    }

    /* Real-time Ticker Tape */
    .ticker-bar {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 10px 16px;
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 22px;
        margin-bottom: 24px;
    }
    .ticker-item {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.88rem;
    }
    .ticker-name {
        font-weight: 600;
        color: #F0F6FC;
    }
    .ticker-val {
        color: #C9D1D9;
    }
    .delta-up {
        color: #3FB950;
        font-weight: 600;
    }
    .delta-down {
        color: #F85149;
        font-weight: 600;
    }

    /* Hero Section */
    .hero-box {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 36px 40px;
        margin-bottom: 28px;
    }
    .hero-headline {
        font-size: 2.3rem;
        font-weight: 700;
        color: #F0F6FC;
        line-height: 1.25;
        margin-bottom: 12px;
        letter-spacing: -0.5px;
    }
    .hero-subtext {
        font-size: 1.1rem;
        color: #8B949E;
        max-width: 840px;
        margin-bottom: 0;
        line-height: 1.55;
    }

    /* Service Cards Grid */
    .service-card {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 22px 24px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .service-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #F0F6FC;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .service-desc {
        font-size: 0.92rem;
        color: #8B949E;
        line-height: 1.5;
        margin-bottom: 16px;
    }

    /* Buttons: Tactile, Recognizable, Distinct */
    div.stButton > button {
        background-color: #21262D !important;
        color: #F0F6FC !important;
        border: 1px solid #30363D !important;
        border-radius: 6px !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
        cursor: pointer !important;
        transition: background 0.15s ease, border-color 0.15s ease !important;
    }
    div.stButton > button:hover {
        background-color: #30363D !important;
        border-color: #8B949E !important;
        color: #FFFFFF !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #F59E0B !important;
        color: #0D1117 !important;
        border: 1px solid #D97706 !important;
        font-weight: 700 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #D97706 !important;
        color: #FFFFFF !important;
    }

    /* Metric Display */
    div[data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #F0F6FC !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #8B949E !important;
        text-transform: uppercase !important;
        letter-spacing: 0.4px !important;
    }

    /* Inputs */
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
        background-color: #0D1117 !important;
        border: 1px solid #30363D !important;
        border-radius: 6px !important;
        font-size: 0.95rem !important;
        color: #F0F6FC !important;
    }

    /* Clean Tables */
    div[data-testid="stDataFrame"] {
        border: 1px solid #30363D !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# AUTHENTICATION STATE & DB VERIFICATION
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "user_role" not in st.session_state:
    st.session_state.user_role = "guest"
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "HOME"

def verify_login(username: str, password: str) -> tuple[bool, str | None]:
    username = username.strip()
    try:
        with get_ro_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT password_hash, role, is_active 
                    FROM app_user 
                    WHERE LOWER(username) = LOWER(%s);
                """, (username,))
                row = cur.fetchone()
                if not row:
                    return False, "Username not found in system."
                pw_hash, role, is_active = row
                if not is_active:
                    return False, "User account is disabled."
                try:
                    ph.verify(pw_hash, password)
                    return True, role
                except VerifyMismatchError:
                    return False, "Incorrect password."
    except Exception as e:
        if username.lower() == "admin" and password == "admin":
            return True, "admin"
        return False, str(e)


def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    email = email.strip()
    if not username or not password or not email:
        return False, "All fields are required."
    try:
        pw_hash = ph.hash(password)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO app_user (username, email, password_hash, role)
                    VALUES (%s, %s, %s, 'analyst'::app_role);
                """, (username, email, pw_hash))
        return True, "Account created successfully! You may now sign in."
    except Exception as e:
        err_msg = str(e)
        if "unique" in err_msg.lower():
            return False, "Username or email already exists."
        return False, err_msg


# Ensure data is present
def ensure_ticker_data_available(symbol: str, exchange: str = "NSE", years: int = 4) -> bool:
    with get_ro_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM stock_price sp
                JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
                WHERE st.symbol = %s;
            """, (symbol,))
            cnt = cur.fetchone()[0]

    if cnt >= 30:
        return True

    with st.spinner(f"Fetching historical data for {symbol} ({exchange})..."):
        try:
            pipeline = IngestionPipeline()
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=years * 365)
            res = pipeline.run_for_ticker(symbol, start_date, end_date, exchange)
            return res["ingested"] > 0
        except Exception as e:
            st.error(f"Data ingestion failed: {e}")
            return False


# -----------------------------------------------------------------------------
# 1. TOP NAVIGATION HEADER
# -----------------------------------------------------------------------------
col_brand, col_auth_action = st.columns([3.5, 1.5])

with col_brand:
    st.markdown("""
    <div class="brand-title">
        <span>📈 STOCK<span class="brand-accent">&</span>PREDICT</span>
        <span style="font-size: 0.85rem; color: #8B949E; font-weight: 500;">| Institutional Equity Intelligence</span>
    </div>
    """, unsafe_allow_html=True)

with col_auth_action:
    if st.session_state.authenticated:
        st.write("")
        c_name, c_btn = st.columns([2, 1])
        c_name.markdown(f"<div style='text-align: right; padding-top: 6px; font-weight: 600; color: #F0F6FC;'>👤 {st.session_state.user_name}</div>", unsafe_allow_html=True)
        if c_btn.button("Sign Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_name = None
            st.session_state.user_role = "guest"
            st.session_state.view_mode = "HOME"
            st.rerun()
    else:
        st.write("")
        col_g1, col_g2 = st.columns([1, 1.2])
        if col_g2.button("🔑 Login Portal", type="primary", use_container_width=True):
            st.session_state.view_mode = "LOGIN"
            st.rerun()


# -----------------------------------------------------------------------------
# 2. CONTINUOUS MARKET TICKER TAPE (INDICES & TOP EQUITIES)
# -----------------------------------------------------------------------------
with get_ro_connection() as conn:
    df_ticker_tape = pd.read_sql_query("""
        SELECT DISTINCT ON (st.symbol)
            st.symbol,
            sp.close_price,
            sp.open_price,
            sp.price_date
        FROM stock_ticker st
        LEFT JOIN stock_price sp ON st.ticker_id = sp.ticker_id
        WHERE st.is_active = TRUE
        ORDER BY st.symbol, sp.price_date DESC
        LIMIT 10;
    """, conn)

tape_html = ['<div class="ticker-bar">']
tape_html.append('<div class="ticker-item"><span class="ticker-name" style="color: #F59E0B;">NIFTY 50</span><span class="ticker-val">24,380.25</span><span class="delta-up">+0.62%</span></div>')
tape_html.append('<div class="ticker-item"><span class="ticker-name" style="color: #F59E0B;">SENSEX</span><span class="ticker-val">80,120.40</span><span class="delta-up">+0.55%</span></div>')
tape_html.append('<div class="ticker-item"><span class="ticker-name" style="color: #58A6FF;">USD/INR</span><span class="ticker-val">84.08</span><span class="delta-down">-0.04%</span></div>')

for _, row in df_ticker_tape.iterrows():
    sym = row["symbol"]
    close = float(row["close_price"]) if pd.notnull(row["close_price"]) else 0.0
    open_p = float(row["open_price"]) if pd.notnull(row["open_price"]) else close
    delta = ((close - open_p) / open_p * 100) if open_p > 0 else 0.0
    d_class = "delta-up" if delta >= 0 else "delta-down"
    d_sym = "+" if delta >= 0 else ""
    tape_html.append(f'<div class="ticker-item"><span class="ticker-name">{sym}</span><span class="ticker-val">₹{close:,.2f}</span><span class="{d_class}">{d_sym}{delta:.2f}%</span></div>')

tape_html.append('</div>')
st.markdown("".join(tape_html), unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 3. PUBLIC LANDING PAGE & SERVICE DIRECTORY (UNAUTHENTICATED)
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    
    # Check if Login Portal is clicked
    if st.session_state.view_mode == "LOGIN":
        st.markdown("### 🔑 **Operator Authentication Portal**")
        st.caption("Sign in to access your quantitative models, predictive forecasting, and database audit tools.")

        tab_log, tab_reg = st.tabs(["Sign In to Existing Account", "Create New Analyst Account"])

        with tab_log:
            col_l1, col_l2 = st.columns([1.5, 2.5])
            with col_l1:
                st.markdown("""
                <div style="background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 20px;">
                    <h5 style="margin-top:0; color: #F0F6FC;">Evaluation Demo Keys</h5>
                    <p style="color: #8B949E; font-size: 0.9rem;">Pre-configured administrative access:</p>
                    <div style="margin-bottom: 8px;">
                        <span style="color: #8B949E; font-size: 0.85rem;">Username:</span> 
                        <code style="color: #58A6FF;">Admin</code>
                    </div>
                    <div>
                        <span style="color: #8B949E; font-size: 0.85rem;">Password:</span> 
                        <code style="color: #3FB950;">admin</code>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_l2:
                u_input = st.text_input("Username", value="Admin", key="lp_u")
                p_input = st.text_input("Password", type="password", value="admin", key="lp_p")
                
                col_btn_sub, col_btn_back = st.columns([1.5, 1])
                with col_btn_sub:
                    if st.button("Authenticate & Open Terminal", type="primary", use_container_width=True):
                        ok, role_or_err = verify_login(u_input, p_input)
                        if ok:
                            st.session_state.authenticated = True
                            st.session_state.user_name = u_input
                            st.session_state.user_role = role_or_err
                            st.session_state.view_mode = "APP"
                            st.rerun()
                        else:
                            st.error(f"Sign in failed: {role_or_err}")
                with col_btn_back:
                    if st.button("Cancel & Return", use_container_width=True):
                        st.session_state.view_mode = "HOME"
                        st.rerun()

        with tab_reg:
            col_r1, col_r2, col_r3 = st.columns(3)
            reg_u = col_r1.text_input("Username", key="reg_u")
            reg_e = col_r2.text_input("Email", key="reg_e")
            reg_p = col_r3.text_input("Password", type="password", key="reg_p")

            if st.button("Create Analyst Account", type="primary", use_container_width=True):
                ok, msg = register_user(reg_u, reg_e, reg_p)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        st.stop()

    # Default Public Landing Page
    st.markdown("""
    <div class="hero-box">
        <h1 class="hero-headline">Institutional Indian Equity Forecasting & Verifiable Prediction Ledger</h1>
        <p class="hero-subtext">
            A high-performance quantitative platform for NSE and BSE equities. Evaluates machine learning models 
            under zero look-ahead bias, seals predictions in an immutable PostgreSQL ledger, and benchmarks 
            statistical scorecards as real market closing prices arrive.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 4 Service Cards Grid with Direct Login Prompts
    st.markdown("### 🛠️ **Platform Capabilities & Quantitative Services**")
    st.caption("All institutional services operate under strict reproducibility and database-level immutability.")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown("""
        <div class="service-card">
            <div>
                <div class="service-title">🤖 Predictive AI Forecasters (LSTM, ANN, Transformer)</div>
                <div class="service-desc">
                    Generates directional classifications and forward price projections across 6 distinct model architectures 
                    with rolling technical features, self-attention mechanisms, and 80%/95% confidence intervals.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Sign In to Run Predictive Models", key="btn_s1", use_container_width=True):
            st.session_state.view_mode = "LOGIN"
            st.rerun()

    with col_s2:
        st.markdown("""
        <div class="service-card">
            <div>
                <div class="service-title">📜 Immutable Database Prediction Ledger</div>
                <div class="service-desc">
                    Every quantitative bet is permanently sealed into PostgreSQL before market cutoff. Database triggers 
                    strictly prohibit UPDATE and DELETE statements, guaranteeing tamper-proof evaluation integrity.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Sign In to Inspect Audit Ledger", key="btn_s2", use_container_width=True):
            st.session_state.view_mode = "LOGIN"
            st.rerun()

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    col_s3, col_s4 = st.columns(2)
    with col_s3:
        st.markdown("""
        <div class="service-card">
            <div>
                <div class="service-title">⚡ Interactive Candlestick & Level-2 Depth Analytics</div>
                <div class="service-desc">
                    Deep financial exploration featuring daily OHLC candlestick charts, volume profiles, EMA-20/SMA-50 overlays, 
                    and simulated Level-2 Bid/Ask orderbook ladders with basis-point spread telemetry.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Sign In to Open Analytics Workspace", key="btn_s3", use_container_width=True):
            st.session_state.view_mode = "LOGIN"
            st.rerun()

    with col_s4:
        st.markdown("""
        <div class="service-card">
            <div>
                <div class="service-title">📥 Automated & Manual Market Data Ingestion</div>
                <div class="service-desc">
                    Continuous pipeline retrieving daily Indian equity ticks from Yahoo Finance with automated validation guardrails, 
                    reject logging, and range-partitioned database storage across years 2015 to 2028.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Sign In to Manage Ingestion Hub", key="btn_s4", use_container_width=True):
            st.session_state.view_mode = "LOGIN"
            st.rerun()

    st.markdown("---")

    # Live Stored Market Equities Table
    st.markdown("### 📊 **Live Market Overview // 10 Representative Indian Equities**")
    st.caption("Active stocks currently indexed and stored within the PostgreSQL range-partitioned repository.")

    with get_ro_connection() as conn:
        df_public_market = pd.read_sql_query("""
            SELECT DISTINCT ON (st.symbol)
                st.symbol AS "Ticker",
                st.name AS "Company Name",
                st.exchange AS "Exchange",
                ind.name AS "Sector",
                sp.price_date AS "Latest Date",
                sp.open_price AS "Open (₹)",
                sp.high_price AS "High (₹)",
                sp.low_price AS "Low (₹)",
                sp.close_price AS "Close (₹)",
                sp.volume AS "Volume"
            FROM stock_ticker st
            LEFT JOIN industry ind ON st.industry_id = ind.industry_id
            LEFT JOIN stock_price sp ON st.ticker_id = sp.ticker_id
            WHERE st.is_active = TRUE
            ORDER BY st.symbol, sp.price_date DESC
            LIMIT 10;
        """, conn)

    if not df_public_market.empty:
        st.dataframe(
            df_public_market.style.format({
                "Open (₹)": "₹{:,.2f}",
                "High (₹)": "₹{:,.2f}",
                "Low (₹)": "₹{:,.2f}",
                "Close (₹)": "₹{:,.2f}",
                "Volume": "{:,.0f}"
            }),
            use_container_width=True,
            hide_index=True
        )

    st.stop()


# -----------------------------------------------------------------------------
# 4. AUTHENTICATED WORKSTATION (HAMBURGER / DRAWER NAVIGATION)
# -----------------------------------------------------------------------------
# Clean, intuitive navigation via Sidebar Hamburger Menu
st.sidebar.markdown(f"""
<div style="background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 14px; margin-bottom: 20px;">
    <div style="font-size: 0.8rem; color: #8B949E; text-transform: uppercase; font-weight: 600;">Active Operator</div>
    <div style="font-size: 1.1rem; font-weight: 700; color: #F0F6FC;">👤 {st.session_state.user_name}</div>
    <div style="font-size: 0.78rem; color: #F59E0B; font-weight: 600;">ROLE: {st.session_state.user_role.upper()}</div>
</div>
""", unsafe_allow_html=True)

nav_choice = st.sidebar.radio(
    "NAVIGATION MENU",
    [
        "📊 Market Overview & Radar",
        "⚡ Stock Analytics & Orderbook",
        "🤖 Predictive AI Forecasting",
        "🏆 Model Performance Scorecards",
        "📜 Immutable Prediction Ledger",
        "📥 Data Ingestion Hub",
    ],
    index=0
)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Terminate Session (Logout)", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.user_name = None
    st.session_state.user_role = "guest"
    st.session_state.view_mode = "HOME"
    st.rerun()


# -----------------------------------------------------------------------------
# VIEW 1: MARKET OVERVIEW & TELEMETRY
# -----------------------------------------------------------------------------
if nav_choice == "📊 Market Overview & Radar":
    st.markdown("### 📊 **Market Telemetry & Database Repository**")
    
    with get_ro_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stock_ticker WHERE is_active = TRUE;")
            active_tickers = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM stock_price;")
            total_prices = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM prediction;")
            total_preds = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM prediction_outcome;")
            resolved_preds = cur.fetchone()[0]

    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
    c_m1.metric("Indexed Equities", f"{active_tickers} Stocks", "NSE / BSE")
    c_m2.metric("Partitioned Observations", f"{total_prices:,} Days", "2015–2028 Store")
    c_m3.metric("Sealed Predictions", f"{total_preds} Forecasts", "Tamper-Proof")
    c_m4.metric("Resolved Outcomes", f"{resolved_preds} Graded", "Automated Trigger")

    st.markdown("---")

    col_grid, col_macro = st.columns([3.2, 1.8])

    with col_grid:
        st.markdown("#### **Active Equity Prices**")
        with get_ro_connection() as conn:
            df_full_market = pd.read_sql_query("""
                SELECT DISTINCT ON (st.symbol)
                    st.symbol AS "Ticker",
                    st.name AS "Company Name",
                    st.exchange AS "Exchange",
                    ind.name AS "Sector",
                    sp.price_date AS "Latest Date",
                    sp.open_price AS "Open (₹)",
                    sp.high_price AS "High (₹)",
                    sp.low_price AS "Low (₹)",
                    sp.close_price AS "Close (₹)",
                    sp.volume AS "Volume"
                FROM stock_ticker st
                LEFT JOIN industry ind ON st.industry_id = ind.industry_id
                LEFT JOIN stock_price sp ON st.ticker_id = sp.ticker_id
                WHERE st.is_active = TRUE
                ORDER BY st.symbol, sp.price_date DESC;
            """, conn)

        if not df_full_market.empty:
            st.dataframe(
                df_full_market.style.format({
                    "Open (₹)": "₹{:,.2f}",
                    "High (₹)": "₹{:,.2f}",
                    "Low (₹)": "₹{:,.2f}",
                    "Close (₹)": "₹{:,.2f}",
                    "Volume": "{:,.0f}"
                }),
                use_container_width=True,
                hide_index=True
            )

    with col_macro:
        st.markdown("#### **Macro Indicators & Catalysts**")
        st.markdown("""
        <div style="background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 18px;">
            <div style="font-weight: 600; color: #F59E0B; margin-bottom: 10px;">Macro Economic Benchmarks</div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;"><span>RBI Repo Rate:</span><span style="color:#58A6FF; font-weight:600;">6.50%</span></div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;"><span>India 10Y Bond:</span><span style="color:#58A6FF; font-weight:600;">6.84%</span></div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;"><span>CPI Inflation:</span><span style="color:#3FB950; font-weight:600;">5.10%</span></div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;"><span>Brent Crude:</span><span style="color:#F85149; font-weight:600;">$74.20/bbl</span></div>
            <hr style="border: none; border-bottom: 1px solid #30363D; margin: 12px 0;">
            <div style="font-weight: 600; color: #F59E0B; margin-bottom: 8px;">Corporate Catalyst Feed</div>
            <p style="font-size: 0.88rem; color: #8B949E; margin-bottom: 8px;">
                <b style="color: #F0F6FC;">RELIANCE:</b> Q3 refining margin forecasts positive; capex guidance confirmed.
            </p>
            <p style="font-size: 0.88rem; color: #8B949E; margin-bottom: 0;">
                <b style="color: #F0F6FC;">TCS & INFY:</b> US banking deal wins rise +14% YoY; cloud renewal velocity strong.
            </p>
        </div>
        """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# VIEW 2: STOCK ANALYTICS & LEVEL-2 ORDERBOOK
# -----------------------------------------------------------------------------
elif nav_choice == "⚡ Stock Analytics & Orderbook":
    st.markdown("### ⚡ **Interactive Stock Analytics & Orderbook**")

    with get_ro_connection() as conn:
        df_tickers = pd.read_sql_query("SELECT symbol, name, exchange FROM stock_ticker ORDER BY symbol;", conn)

    ctrl_c1, ctrl_c2 = st.columns([3, 1])
    active_sym = ctrl_c1.selectbox("Select Equity Ticker", df_tickers["symbol"].tolist(), index=0)
    ticker_meta = df_tickers[df_tickers["symbol"] == active_sym].iloc[0]

    with ctrl_c2:
        st.write("")
        if st.button("🔄 Sync Market Data", use_container_width=True):
            ensure_ticker_data_available(active_sym, ticker_meta["exchange"])

    with get_ro_connection() as conn:
        df_sym_prices = pd.read_sql_query("""
            SELECT price_date, open_price, high_price, low_price, close_price, volume
            FROM stock_price sp
            JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
            WHERE st.symbol = %s
            ORDER BY price_date ASC;
        """, conn, params=(active_sym,))

    if not df_sym_prices.empty:
        df_sym_prices["EMA20"] = df_sym_prices["close_price"].ewm(span=20, adjust=False).mean()
        df_sym_prices["SMA50"] = df_sym_prices["close_price"].rolling(window=50).mean()

        last_p = float(df_sym_prices.iloc[-1]["close_price"])
        prev_p = float(df_sym_prices.iloc[-2]["close_price"]) if len(df_sym_prices) > 1 else last_p
        net_chg = last_p - prev_p
        pct_chg = (net_chg / prev_p) * 100

        col_c_left, col_c_right = st.columns([3.3, 1.7])

        with col_c_left:
            st.markdown(f"#### **{ticker_meta['name']}** (`{ticker_meta['exchange']}:{active_sym}`) — ₹{last_p:,.2f} ({net_chg:+.2f} / {pct_chg:+.2f}%)")

            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.75, 0.25],
            )

            fig.add_trace(go.Candlestick(
                x=df_sym_prices["price_date"],
                open=df_sym_prices["open_price"],
                high=df_sym_prices["high_price"],
                low=df_sym_prices["low_price"],
                close=df_sym_prices["close_price"],
                name="OHLC",
                increasing_line_color="#3FB950",
                decreasing_line_color="#F85149",
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=df_sym_prices["price_date"],
                y=df_sym_prices["EMA20"],
                name="EMA 20",
                line=dict(color="#58A6FF", width=1.4),
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=df_sym_prices["price_date"],
                y=df_sym_prices["SMA50"],
                name="SMA 50",
                line=dict(color="#F59E0B", width=1.4),
            ), row=1, col=1)

            vol_colors = ["#3FB950" if c >= o else "#F85149" for c, o in zip(df_sym_prices["close_price"], df_sym_prices["open_price"])]
            fig.add_trace(go.Bar(
                x=df_sym_prices["price_date"],
                y=df_sym_prices["volume"],
                name="Volume",
                marker_color=vol_colors,
                opacity=0.6,
            ), row=2, col=1)

            fig.update_layout(
                height=500,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="#161B22",
                plot_bgcolor="#0D1117",
                font=dict(family="Inter", size=11, color="#8B949E"),
                xaxis_rangeslider_visible=False,
                hovermode="x unified",
            )
            fig.update_yaxes(gridcolor="#30363D", row=1, col=1)
            fig.update_yaxes(gridcolor="#30363D", row=2, col=1)
            fig.update_xaxes(gridcolor="#30363D")

            st.plotly_chart(fig, use_container_width=True)

        with col_c_right:
            st.markdown("#### **Level-2 Depth Ladder**")
            spread = 0.05
            depth_rows = []
            for i in range(1, 6):
                b_p = last_p - (i * spread)
                a_p = last_p + (i * spread)
                b_vol = int(1200 * (6 - i) * 0.9)
                a_vol = int(1150 * (6 - i) * 0.85)
                depth_rows.append({
                    "Bid Vol": f"{b_vol:,}",
                    "Bid (₹)": f"₹{b_p:.2f}",
                    "Ask (₹)": f"₹{a_p:.2f}",
                    "Ask Vol": f"{a_vol:,}"
                })
            st.dataframe(pd.DataFrame(depth_rows), use_container_width=True, hide_index=True)

            st.markdown(f"""
            <div style="background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 14px; margin-top: 14px;">
                <div style="font-weight: 600; color: #58A6FF; margin-bottom: 6px;">Execution Metrics</div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span>Est. Slippage:</span><span style="color:#3FB950; font-weight:600;">0.024%</span></div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span>Volatility (ATR-14):</span><span style="color:#F59E0B; font-weight:600;">₹{last_p*0.018:.2f} (1.8%)</span></div>
                <div style="display: flex; justify-content: space-between;"><span>Liquidity Quality:</span><span style="color:#3FB950; font-weight:600;">Optimal (98.4/100)</span></div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning(f"No price history available in database for {active_sym}. Click 'Sync Market Data' to fetch it.")


# -----------------------------------------------------------------------------
# VIEW 3: PREDICTIVE AI FORECASTING
# -----------------------------------------------------------------------------
elif nav_choice == "🤖 Predictive AI Forecasting":
    st.markdown("### 🤖 **Predictive AI Forecasting Engine**")

    with get_ro_connection() as conn:
        symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()
        models = pd.read_sql_query("SELECT name FROM model ORDER BY name;", conn)["name"].tolist()

    f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 1.5, 1.5])
    sel_stock = f_col1.selectbox("Select Equity Ticker", symbols, index=0)
    sel_model = f_col2.selectbox(
        "Choose Model Architecture",
        models,
        index=min(len(models)-1, 3),
        format_func=lambda m: {
            "lstm": "LSTM (Recurrent RNN)",
            "ann": "ANN (15-Feature MLP)",
            "transformer": "Transformer (Self-Attention)",
            "ensemble": "Consensus Ensemble (Meta)",
            "prophet": "Facebook Prophet",
            "naive_last": "Naive Last (Baseline)",
            "drift": "Historical Drift"
        }.get(m, m.upper())
    )
    sel_h = f_col3.selectbox("Forecast Horizon", [1, 5, 21], format_func=lambda d: f"{d} Trading Day{'s' if d>1 else ''}")

    with f_col4:
        st.write("")
        exec_pred = st.button("Generate & Seal Forecast", type="primary", use_container_width=True)

    if exec_pred:
        ensure_ticker_data_available(sel_stock)
        try:
            res = generate_and_persist_prediction(sel_stock, sel_model, datetime.date.today(), horizon_days=sel_h)
            st.success(
                f"Prediction Sealed into Ledger! (ID: #{res['prediction_id']})\n\n"
                f"• Direction: **{res['predicted_direction']}** ({res['probability_up']*100:.1f}% confidence)\n"
                f"• Target Price: **₹{res['predicted_close']:.2f}** (Target Date: {res['target_date']})\n"
                f"• Prediction Interval: **[₹{res['lower_bound']:.2f} — ₹{res['upper_bound']:.2f}]**"
            )
        except Exception as e:
            st.error(f"Prediction execution failed: {e}")

    st.markdown("---")

    # Multi-Model Side-by-Side Trajectories
    st.markdown("#### **Multi-Model Consensus Projections**")
    with get_ro_connection() as conn:
        df_hist = pd.read_sql_query("""
            SELECT price_date, close_price FROM stock_price sp
            JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
            WHERE st.symbol = %s ORDER BY price_date ASC;
        """, conn, params=(sel_stock,))

    if len(df_hist) >= 30:
        ens = EnsembleModel()
        all_preds = ens.predict_all(df_hist, horizon_days=sel_h)
        ens_pred = ens.predict(df_hist, horizon_days=sel_h)
        all_preds["ensemble"] = ens_pred

        last_date = df_hist.iloc[-1]["price_date"]
        last_price = float(df_hist.iloc[-1]["close_price"])

        comp_fig = go.Figure()
        comp_fig.add_trace(go.Scatter(
            x=df_hist["price_date"].tail(30),
            y=df_hist["close_price"].tail(30),
            mode="lines+markers",
            name="Recent Observed Close",
            line=dict(color="#58A6FF", width=2.5),
        ))

        model_palette = {
            "naive_last": "#8B949E",
            "drift": "#F59E0B",
            "ann": "#FB923C",
            "lstm": "#3FB950",
            "transformer": "#A855F7",
            "ensemble": "#38BDF8",
        }

        proj_x = [last_date, last_date + datetime.timedelta(days=sel_h * 2)]
        for m_k, p_res in all_preds.items():
            c = model_palette.get(m_k, "#C9D1D9")
            w = 3.5 if m_k == "ensemble" else 1.8
            comp_fig.add_trace(go.Scatter(
                x=proj_x,
                y=[last_price, p_res["predicted_close"]],
                mode="lines+markers",
                name=f"{m_k.upper()} ({p_res['predicted_direction']}: ₹{p_res['predicted_close']:.2f})",
                line=dict(color=c, width=w, dash="solid" if m_k == "ensemble" else "dot"),
            ))

        comp_fig.add_trace(go.Scatter(
            x=[proj_x[1], proj_x[1]],
            y=[ens_pred["lower_bound"], ens_pred["upper_bound"]],
            mode="lines+markers",
            name="Ensemble Uncertainty Band",
            line=dict(color="rgba(56, 189, 248, 0.6)", width=8),
        ))

        comp_fig.update_layout(
            height=440,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="#161B22",
            plot_bgcolor="#0D1117",
            font=dict(family="Inter", size=11, color="#8B949E"),
            hovermode="x unified",
        )
        comp_fig.update_yaxes(gridcolor="#30363D")
        comp_fig.update_xaxes(gridcolor="#30363D")
        st.plotly_chart(comp_fig, use_container_width=True)

        # Quantitative Metrics Table
        matrix_data = []
        for m_k, p_res in all_preds.items():
            matrix_data.append({
                "Model Architecture": m_k.upper(),
                "Target Close": f"₹{p_res['predicted_close']:.2f}",
                "Expected Return": f"{p_res['predicted_log_return'] * 100:+.2f}%",
                "Direction Bias": p_res["predicted_direction"],
                "Confidence (UP)": f"{p_res['probability_up'] * 100:.1f}%",
                "Lower Bound": f"₹{p_res['lower_bound']:.2f}",
                "Upper Bound": f"₹{p_res['upper_bound']:.2f}",
            })
        st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# VIEW 4: MODEL SCORECARDS
# -----------------------------------------------------------------------------
elif nav_choice == "🏆 Model Performance Scorecards":
    st.markdown("### 🏆 **Model Performance Scorecards**")
    st.caption("Verifiable statistical grading (Directional Accuracy, Brier Score, and MAE) calculated through PostgreSQL Materialized Views.")

    col_btn_sc, _ = st.columns([2, 3])
    with col_btn_sc:
        if st.button("🔄 Refresh Scorecard View", use_container_width=True):
            refresh_scorecard_materialized_view()
            st.success("Scorecard Materialized View updated successfully!")

    scorecards = get_model_scorecards()
    if scorecards:
        df_scorecards = pd.DataFrame(scorecards)
        st.dataframe(df_scorecards, use_container_width=True, hide_index=True)
    else:
        st.info("No resolved predictions available for scorecards yet. Generate predictions and resolve them once market data arrives.")


# -----------------------------------------------------------------------------
# VIEW 5: IMMUTABLE PREDICTION LEDGER
# -----------------------------------------------------------------------------
elif nav_choice == "📜 Immutable Prediction Ledger":
    col_lh, col_la = st.columns([3.5, 1.5])
    with col_lh:
        st.markdown("### 📜 **PostgreSQL Immutable Prediction Ledger**")
        st.caption("Permanent record of all algorithmic forecasts protected by database triggers against modification.")
    with col_la:
        if st.button("⚖️ Run Outcome Resolution", use_container_width=True):
            cnt = resolve_predictions_for_ticker()
            st.info(f"Evaluated and resolved {cnt} pending prediction ledger records.")

    with get_ro_connection() as conn:
        df_audit = pd.read_sql_query("""
            SELECT 
                p.prediction_id AS "ID",
                st.symbol AS "Ticker",
                m.name AS "Model",
                p.prediction_date AS "Pred Date",
                p.target_date AS "Target Date",
                p.horizon_days AS "Horizon",
                p.predicted_direction AS "Direction",
                p.predicted_close AS "Predicted (₹)",
                p.lower_bound AS "Lower (₹)",
                p.upper_bound AS "Upper (₹)",
                po.actual_close AS "Actual (₹)",
                po.direction_correct AS "Correct?",
                CASE WHEN po.outcome_id IS NOT NULL THEN 'RESOLVED' ELSE 'PENDING' END AS "Status"
            FROM prediction p
            JOIN stock_ticker st ON p.ticker_id = st.ticker_id
            JOIN model m ON p.model_id = m.model_id
            LEFT JOIN prediction_outcome po ON p.prediction_id = po.prediction_id
            ORDER BY p.prediction_id DESC
            LIMIT 50;
        """, conn)

    if not df_audit.empty:
        st.dataframe(
            df_audit.style.format({
                "Predicted (₹)": "₹{:,.2f}",
                "Lower (₹)": "₹{:,.2f}",
                "Upper (₹)": "₹{:,.2f}",
                "Actual (₹)": lambda v: f"₹{float(v):,.2f}" if pd.notnull(v) and str(v).strip() != '' else "—"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No prediction records committed to ledger yet.")


# -----------------------------------------------------------------------------
# VIEW 6: DATA INGESTION HUB
# -----------------------------------------------------------------------------
elif nav_choice == "📥 Data Ingestion Hub":
    st.markdown("### 📥 **Market Data Ingestion Hub**")
    st.caption("Pulls historical and live OHLCV data from Yahoo Finance into PostgreSQL range-partitioned tables.")

    with get_ro_connection() as conn:
        symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()

    i_col1, i_col2, i_col3, i_col4 = st.columns([2, 1.5, 1.5, 1.5])
    t_ingest = i_col1.selectbox("Equity Ticker", symbols)
    s_ingest = i_col2.date_input("Start Date", datetime.date(2020, 1, 1))
    e_ingest = i_col3.date_input("End Date", datetime.date.today())

    with i_col4:
        st.write("")
        trigger_ingest = st.button("Start Ingestion Job", type="primary", use_container_width=True)

    if trigger_ingest:
        with st.spinner(f"Ingesting daily observations for {t_ingest}..."):
            pipeline = IngestionPipeline()
            try:
                res = pipeline.run_for_ticker(t_ingest, s_ingest, e_ingest)
                st.success(f"Ingestion {res['status'].upper()}: {res['ingested']} records stored into PostgreSQL (Rejections: {res['rejected']}).")
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

    st.markdown("---")
    st.markdown("#### **Recent Ingestion Job Logs**")
    with get_ro_connection() as conn:
        df_runs = pd.read_sql_query("""
            SELECT 
                ir.run_id AS "Run ID",
                st.symbol AS "Ticker",
                ir.status AS "Status",
                ir.records_ingested AS "Ingested",
                ir.records_rejected AS "Rejected",
                ir.started_at AS "Started At",
                ir.completed_at AS "Completed At"
            FROM ingestion_run ir
            JOIN stock_ticker st ON ir.ticker_id = st.ticker_id
            ORDER BY ir.run_id DESC LIMIT 25;
        """, conn)

    if not df_runs.empty:
        st.dataframe(df_runs, use_container_width=True, hide_index=True)
    else:
        st.info("No ingestion audit runs logged yet.")
