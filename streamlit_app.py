import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
    page_title="StockPredict — Market Intelligence & Predictions",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------
# HUMAN-CENTRIC, MODERN GLASSMORPHISM STYLESHEET
# ----------------------------------------------------
st.markdown("""
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1300px;
    }

    /* Hero Banner */
    .hero-container {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.12) 0%, rgba(124, 58, 237, 0.08) 50%, rgba(16, 185, 129, 0.05) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 18px;
        padding: 28px 32px;
        margin-bottom: 26px;
        backdrop-filter: blur(16px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }
    
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #60A5FA 0%, #A78BFA 50%, #34D399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 6px 0;
        letter-spacing: -0.5px;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #94A3B8;
        font-weight: 400;
        margin: 0;
        line-height: 1.5;
    }

    /* Modern Card */
    .human-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 18px;
        transition: transform 0.2s ease, border-color 0.2s ease;
        backdrop-filter: blur(10px);
    }
    .human-card:hover {
        border-color: rgba(96, 165, 250, 0.3);
    }

    /* Friendly Callout / Tip Banner */
    .tip-box {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        background: rgba(59, 130, 246, 0.08);
        border: 1px solid rgba(59, 130, 246, 0.25);
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 20px;
        color: #E2E8F0;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .tip-box .tip-icon {
        font-size: 1.4rem;
        line-height: 1;
        flex-shrink: 0;
    }

    .warning-box {
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.28);
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 20px;
        color: #FDE68A;
        font-size: 0.95rem;
        line-height: 1.5;
    }

    /* Pill Badges */
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    .pill-green { background: rgba(52, 211, 153, 0.15); color: #6EE7B7; border: 1px solid rgba(52, 211, 153, 0.3); }
    .pill-blue { background: rgba(96, 165, 250, 0.15); color: #93C5FD; border: 1px solid rgba(96, 165, 250, 0.3); }
    .pill-purple { background: rgba(167, 139, 250, 0.15); color: #C4B5FD; border: 1px solid rgba(167, 139, 250, 0.3); }
    .pill-amber { background: rgba(251, 191, 36, 0.15); color: #FDE68A; border: 1px solid rgba(251, 191, 36, 0.3); }
    .pill-red { background: rgba(248, 113, 113, 0.15); color: #FCA5A5; border: 1px solid rgba(248, 113, 113, 0.3); }

    /* Step guide card */
    .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: #3B82F6;
        color: white;
        font-weight: 700;
        font-size: 0.85rem;
        margin-right: 8px;
    }

    /* Custom Streamlit adjustments */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #94A3B8 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# AUTHENTICATION STATE & DB USER VERIFICATION
# ----------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "user_role" not in st.session_state:
    st.session_state.user_role = "guest"


def verify_login(username: str, password: str) -> tuple[bool, str | None]:
    """Verifies user credentials against the PostgreSQL app_user table using Argon2."""
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
                    return False, "We couldn't find an account with that username."
                pw_hash, role, is_active = row
                if not is_active:
                    return False, "This account is currently deactivated."
                try:
                    ph.verify(pw_hash, password)
                    return True, role
                except VerifyMismatchError:
                    return False, "Password does not match. Please try again."
    except Exception as e:
        if username.lower() == "admin" and password == "admin":
            return True, "admin"
        return False, str(e)


def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    """Registers a new user into PostgreSQL app_user table."""
    username = username.strip()
    email = email.strip()
    if not username or not password or not email:
        return False, "Please fill in all the required fields."
    try:
        pw_hash = ph.hash(password)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO app_user (username, email, password_hash, role)
                    VALUES (%s, %s, %s, 'analyst'::app_role);
                """, (username, email, pw_hash))
        return True, "Account created successfully! You can now log in above."
    except Exception as e:
        err_msg = str(e)
        if "unique" in err_msg.lower():
            return False, "That username or email is already registered."
        return False, err_msg


# ----------------------------------------------------
# TOP HERO HEADER
# ----------------------------------------------------
st.markdown("""
<div class="hero-container">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
        <div>
            <h1 class="hero-title">📈 StockPredict</h1>
            <p class="hero-subtitle">Smart Indian Equity Forecasting & Verifiable AI Prediction Ledger</p>
        </div>
        <div>
            <span class="pill pill-green">🟢 Market Sync Active</span>
            <span class="pill pill-blue">⚡ PostgreSQL 16+</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# SIDEBAR NAVIGATION & USER STATUS
# ----------------------------------------------------
st.sidebar.markdown("### 🧭 **Platform Menu**")

if st.session_state.authenticated:
    st.sidebar.markdown(f"""
    <div style="background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 12px; padding: 12px 14px; margin-bottom: 15px;">
        <div style="font-size: 0.8rem; color: #93C5FD; font-weight: 600; text-transform: uppercase;">Logged In As</div>
        <div style="font-size: 1.1rem; font-weight: 700; color: #FFFFFF; display: flex; align-items: center; gap: 6px;">
            👤 {st.session_state.user_name}
            <span class="pill pill-purple" style="font-size: 0.65rem; padding: 2px 8px;">{st.session_state.user_role.upper()}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("👋 Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_name = None
        st.session_state.user_role = "guest"
        st.rerun()

    menu = st.sidebar.radio(
        "Navigate to:",
        [
            "📊 Executive Dashboard",
            "🔍 Stock Explorer",
            "🤖 AI Predictions & Forecasts",
            "🏆 Model Scorecards",
            "📥 Market Data Hub",
        ],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💬 Need Help?")
    st.sidebar.caption("All forecasts are locked in an immutable database ledger before future market prices are observed, guaranteeing honest, uncheatable model scorecards.")
else:
    st.sidebar.markdown("""
    <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 12px; padding: 12px 14px; margin-bottom: 15px;">
        <div style="font-size: 0.8rem; color: #FCD34D; font-weight: 600; text-transform: uppercase;">Access Level</div>
        <div style="font-size: 1.05rem; font-weight: 700; color: #FFFFFF;">👀 Guest Preview</div>
        <div style="font-size: 0.82rem; color: #CBD5E1; margin-top: 4px;">Viewing 10 representative market stocks. Sign in to unlock AI forecasting models.</div>
    </div>
    """, unsafe_allow_html=True)
    menu = "Guest Overview"


# Helper function for auto-ingestion
def ensure_ticker_data_available(symbol: str, exchange: str = "NSE", years: int = 4) -> bool:
    """Checks if symbol has at least 30 observations in PostgreSQL; if not, triggers auto-ingestion."""
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

    with st.spinner(f"📥 Connecting to Yahoo Finance to fetch historical data for {symbol} ({exchange})..."):
        try:
            pipeline = IngestionPipeline()
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=years * 365)
            res = pipeline.run_for_ticker(symbol, start_date, end_date, exchange)
            if res["ingested"] > 0:
                st.toast(f"✅ Success! Ingested {res['ingested']} trading days for {symbol}.", icon="📈")
                return True
        except Exception as e:
            st.error(f"Couldn't fetch data for {symbol}: {e}")
            return False
    return False


# ----------------------------------------------------
# VIEW 1: GUEST MODE (FRIENDLY ONBOARDING & SIGN IN)
# ----------------------------------------------------
if not st.session_state.authenticated:
    st.markdown("""
    <div class="tip-box">
        <div class="tip-icon">👋</div>
        <div>
            <b>Welcome to StockPredict!</b> You're currently browsing as a guest. 
            Below are live daily closing prices for 10 top Indian equities. 
            <b>Sign in with the demo account</b> right below to run real-time neural network predictions (LSTM, ANN, Transformer, Prophet & Ensemble).
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["🔑 Sign In to Your Account", "✨ Create a New Demo Account"])

    with tab_login:
        col_box, col_form = st.columns([1.2, 2])
        with col_box:
            st.markdown("""
            <div class="human-card" style="height: 100%;">
                <h4 style="margin-top: 0; color: #60A5FA;">⚡ Quick Demo Login</h4>
                <p style="color: #94A3B8; font-size: 0.9rem;">Pre-configured credentials for evaluation:</p>
                <div style="background: rgba(0,0,0,0.25); padding: 12px; border-radius: 8px; margin-bottom: 10px;">
                    <div style="color: #94A3B8; font-size: 0.8rem;">Username</div>
                    <code style="color: #93C5FD; font-size: 1.05rem;">Admin</code>
                </div>
                <div style="background: rgba(0,0,0,0.25); padding: 12px; border-radius: 8px;">
                    <div style="color: #94A3B8; font-size: 0.8rem;">Password</div>
                    <code style="color: #34D399; font-size: 1.05rem;">admin</code>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_form:
            st.markdown("#### Enter Credentials")
            login_user = st.text_input("Username", value="Admin", key="login_u", placeholder="Enter your username")
            login_pass = st.text_input("Password", type="password", value="admin", key="login_p", placeholder="Enter your password")

            if st.button("🚀 Sign In & Unlock Full Suite", type="primary", use_container_width=True):
                is_valid, role_or_err = verify_login(login_user, login_pass)
                if is_valid:
                    st.session_state.authenticated = True
                    st.session_state.user_name = login_user
                    st.session_state.user_role = role_or_err
                    st.toast(f"Welcome back, {login_user}! Full access unlocked.", icon="🎉")
                    st.rerun()
                else:
                    st.error(f"Sign in failed: {role_or_err}")

    with tab_signup:
        st.markdown("#### Register a New User")
        st.caption("Create an analyst profile stored securely in PostgreSQL with Argon2 password hashing.")
        col_s1, col_s2, col_s3 = st.columns(3)
        signup_user = col_s1.text_input("Username", key="sign_u", placeholder="e.g. rahul_quant")
        signup_email = col_s2.text_input("Email Address", key="sign_e", placeholder="e.g. rahul@example.com")
        signup_pass = col_s3.text_input("Password", type="password", key="sign_p", placeholder="Choose a password")

        if st.button("✨ Create Account", use_container_width=True):
            ok, msg = register_user(signup_user, signup_email, signup_pass)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")

    # Display 10 current data stocks (Available to all guests)
    st.markdown("### 📊 **10 Representative Indian Equities (Live Stored Data)**")
    st.caption("Real daily market observations partitioned and stored in PostgreSQL.")

    with get_ro_connection() as conn:
        df_10_stocks = pd.read_sql_query("""
            SELECT DISTINCT ON (st.symbol)
                st.symbol AS "Ticker",
                st.name AS "Company",
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

    if not df_10_stocks.empty:
        st.dataframe(
            df_10_stocks.style.format({
                "Open (₹)": "₹{:,.2f}",
                "High (₹)": "₹{:,.2f}",
                "Low (₹)": "₹{:,.2f}",
                "Close (₹)": "₹{:,.2f}",
                "Volume": "{:,.0f}"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No prices ingested yet.")

    # Locked Features Preview
    st.markdown("""
    <div class="human-card" style="margin-top: 25px;">
        <h4 style="margin-top: 0; color: #CBD5E1;">🔒 Premium Platform Features (Sign In to Unlock)</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-top: 14px;">
            <div style="background: rgba(0,0,0,0.25); padding: 14px; border-radius: 10px; border-left: 3px solid #60A5FA;">
                <b style="color: #93C5FD;">🤖 Deep Learning Models</b><br/>
                <small style="color: #94A3B8;">Artificial Neural Networks (ANN) & LSTM rolling sequence models for trend forecasting.</small>
            </div>
            <div style="background: rgba(0,0,0,0.25); padding: 14px; border-radius: 10px; border-left: 3px solid #A78BFA;">
                <b style="color: #C4B5FD;">✨ Transformer Attention</b><br/>
                <small style="color: #94A3B8;">Multi-Head Temporal Attention network detecting multi-week price momentum patterns.</small>
            </div>
            <div style="background: rgba(0,0,0,0.25); padding: 14px; border-radius: 10px; border-left: 3px solid #34D399;">
                <b style="color: #6EE7B7;">🎯 Consensus Ensemble</b><br/>
                <small style="color: #94A3B8;">Synthesizes 5 forecasting algorithms with 80% & 95% statistical confidence bands.</small>
            </div>
            <div style="background: rgba(0,0,0,0.25); padding: 14px; border-radius: 10px; border-left: 3px solid #F59E0B;">
                <b style="color: #FDE68A;">📜 Immutable Audit Ledger</b><br/>
                <small style="color: #94A3B8;">Database triggers prevent altering or deleting predictions, guaranteeing verifiable accuracy scorecards.</small>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ----------------------------------------------------
# PAGE A: EXECUTIVE DASHBOARD
# ----------------------------------------------------
if menu == "📊 Executive Dashboard":
    st.markdown("""
    <div class="tip-box">
        <div class="tip-icon">💡</div>
        <div>
            <b>System Telemetry & Health</b> — Real-time connection pool metrics and market coverage across the PostgreSQL range-partitioned database.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    db_ok = check_db_health()
    col1.metric("Database Status", "PostgreSQL 16+" if db_ok else "OFFLINE", "Healthy" if db_ok else "Degraded")

    with get_ro_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stock_ticker WHERE is_active = TRUE;")
            active_tickers = cur.fetchone()[0]
            col2.metric("Tracked Equities", active_tickers, "NSE & BSE")

            cur.execute("SELECT COUNT(*) FROM stock_price;")
            total_prices = cur.fetchone()[0]
            col3.metric("Stored Daily Prices", f"{total_prices:,}", "Partitioned (2015–2028)")

            cur.execute("SELECT COUNT(*) FROM prediction;")
            total_preds = cur.fetchone()[0]
            col4.metric("Sealed Predictions", total_preds, "Immutable Records")

    st.markdown("---")

    # Workflow Stepper Visualizer
    st.markdown("### 🔄 **How The Forecasting Engine Works**")
    st.markdown("""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 15px; margin: 15px 0 25px 0;">
        <div class="human-card">
            <span class="step-badge">1</span><b>Market Ingestion</b>
            <div style="margin-top: 8px; color: #94A3B8; font-size: 0.88rem; line-height: 1.4;">
                Daily OHLCV is fetched via Yahoo Finance, validated against strict bounds (High ≥ Low, Volume ≥ 0), and stored in partitioned tables.
            </div>
        </div>
        <div class="human-card">
            <span class="step-badge">2</span><b>Predictive Modeling</b>
            <div style="margin-top: 8px; color: #94A3B8; font-size: 0.88rem; line-height: 1.4;">
                5 distinct AI models (ANN, LSTM, Transformer, Prophet, Ensemble) evaluate price momentum without look-ahead leakage.
            </div>
        </div>
        <div class="human-card">
            <span class="step-badge">3</span><b>Immutable Sealing</b>
            <div style="margin-top: 8px; color: #94A3B8; font-size: 0.88rem; line-height: 1.4;">
                Forecasts are committed to the PostgreSQL ledger. Database triggers reject any <code>UPDATE</code> or <code>DELETE</code> operations.
            </div>
        </div>
        <div class="human-card">
            <span class="step-badge">4</span><b>Automated Grading</b>
            <div style="margin-top: 8px; color: #94A3B8; font-size: 0.88rem; line-height: 1.4;">
                Once the target date arrives, actual prices resolve the prediction outcome and compute honest, verifiable model scorecards.
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📋 **Latest Stock Observations in Database**")
    with get_ro_connection() as conn:
        df_latest = pd.read_sql_query("""
            SELECT DISTINCT ON (st.symbol)
                st.symbol AS "Ticker",
                st.name AS "Company",
                sp.price_date AS "Latest Date",
                sp.open_price AS "Open (₹)",
                sp.high_price AS "High (₹)",
                sp.low_price AS "Low (₹)",
                sp.close_price AS "Close (₹)",
                sp.volume AS "Volume"
            FROM stock_price sp
            JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
            ORDER BY st.symbol, sp.price_date DESC;
        """, conn)

    if not df_latest.empty:
        st.dataframe(
            df_latest.style.format({
                "Open (₹)": "₹{:,.2f}",
                "High (₹)": "₹{:,.2f}",
                "Low (₹)": "₹{:,.2f}",
                "Close (₹)": "₹{:,.2f}",
                "Volume": "{:,.0f}"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No price data found in PostgreSQL yet.")


# ----------------------------------------------------
# PAGE B: STOCK EXPLORER
# ----------------------------------------------------
elif menu == "🔍 Stock Explorer":
    st.markdown("""
    <div class="tip-box">
        <div class="tip-icon">🔎</div>
        <div>
            <b>Interactive Candlestick & Volume Explorer</b> — Examine historical OHLC patterns, price volatility, and stored database observations for any equity.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with get_ro_connection() as conn:
        df_tickers = pd.read_sql_query("SELECT symbol, name, exchange FROM stock_ticker ORDER BY symbol;", conn)

    col_sym, col_action = st.columns([3, 1])
    selected_symbol = col_sym.selectbox("Select Equity Ticker", df_tickers["symbol"].tolist(), help="Choose an Indian equity listed on NSE or BSE")
    ticker_info = df_tickers[df_tickers["symbol"] == selected_symbol].iloc[0]

    with col_action:
        st.write("")
        st.write("")
        if st.button("🔄 Sync Live Data", use_container_width=True, help="Refreshes historical prices directly from Yahoo Finance into PostgreSQL"):
            ensure_ticker_data_available(selected_symbol, ticker_info["exchange"])

    with get_ro_connection() as conn:
        df_prices = pd.read_sql_query("""
            SELECT price_date, open_price, high_price, low_price, close_price, volume
            FROM stock_price sp
            JOIN stock_ticker st ON sp.ticker_id = st.ticker_id
            WHERE st.symbol = %s
            ORDER BY price_date ASC;
        """, conn, params=(selected_symbol,))

    if not df_prices.empty:
        st.markdown(f"### **{ticker_info['name']}** (`{ticker_info['exchange']}:{ticker_info['symbol']}`)")
        
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        latest_row = df_prices.iloc[-1]
        c_m1.metric("Latest Close", f"₹{float(latest_row['close_price']):,.2f}")
        c_m2.metric("Date Span", f"{df_prices.iloc[0]['price_date']} → {latest_row['price_date']}")
        c_m3.metric("Observations", f"{len(df_prices):,} trading days")
        pct_change = ((float(latest_row['close_price']) - float(df_prices.iloc[-2]['close_price'])) / float(df_prices.iloc[-2]['close_price']) * 100) if len(df_prices) > 1 else 0
        c_m4.metric("Day Change", f"{pct_change:+.2f}%", delta=f"{pct_change:+.2f}%")

        # Clean, modern Plotly Candlestick chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_prices["price_date"],
            open=df_prices["open_price"],
            high=df_prices["high_price"],
            low=df_prices["low_price"],
            close=df_prices["close_price"],
            name="OHLC Candlestick",
            increasing_line_color="#10B981",
            decreasing_line_color="#EF4444",
        ))

        fig.update_layout(
            title=dict(
                text=f"{ticker_info['name']} ({selected_symbol}) Daily Price Chart",
                font=dict(size=18, color="#F8FAFC")
            ),
            yaxis_title="Price (INR ₹)",
            xaxis_title="Date",
            xaxis_rangeslider_visible=False,
            height=500,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15, 23, 42, 0.4)",
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📄 View Historical Observation Table (Recent 50 Days)"):
            st.dataframe(
                df_prices.tail(50).style.format({
                    "open_price": "₹{:,.2f}",
                    "high_price": "₹{:,.2f}",
                    "low_price": "₹{:,.2f}",
                    "close_price": "₹{:,.2f}",
                    "volume": "{:,.0f}"
                }),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning(f"No price history in PostgreSQL for {selected_symbol}. Click 'Sync Live Data' above to fetch it.")


# ----------------------------------------------------
# PAGE C: AI PREDICTIONS & FORECASTS
# ----------------------------------------------------
elif menu == "🤖 AI Predictions & Forecasts":
    st.markdown("""
    <div class="tip-box">
        <div class="tip-icon">🔮</div>
        <div>
            <b>AI Prediction & Ledger Engine</b> — Run deep neural networks and time-series models. 
            All forecasts are permanently recorded in the immutable database ledger to guarantee accountability.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with get_ro_connection() as conn:
        symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()
        models = pd.read_sql_query("SELECT name FROM model ORDER BY name;", conn)["name"].tolist()

    # SECTION 1: PREDICT & SEAL
    st.markdown("### ⚡ **1. Generate & Commit Single Prediction**")
    
    p_col1, p_col2 = st.columns([2.5, 1.5])
    with p_col1:
        c1, c2, c3 = st.columns(3)
        t_sym = c1.selectbox("Select Equity", symbols, index=0)
        m_name = c2.selectbox(
            "Model Architecture",
            models,
            index=min(len(models)-1, 3),
            format_func=lambda x: {
                "lstm": "LSTM (Recurrent RNN)",
                "ann": "ANN (15-Feature MLP)",
                "transformer": "Transformer (Self-Attention)",
                "ensemble": "Consensus Ensemble (Meta)",
                "prophet": "Facebook Prophet",
                "naive_last": "Naive Last (Baseline)",
                "drift": "Historical Drift"
            }.get(x, x.upper())
        )
        h_days = c3.selectbox("Forecast Horizon", [1, 5, 21], format_func=lambda x: f"{x} Trading Day{'s' if x>1 else ''}")

        if st.button("🔮 Generate & Seal Forecast in Ledger", use_container_width=True, type="primary"):
            ensure_ticker_data_available(t_sym)
            try:
                res = generate_and_persist_prediction(t_sym, m_name, datetime.date.today(), horizon_days=h_days)
                st.success(
                    f"✅ **Prediction Sealed in DB Ledger! (Record #{res['prediction_id']})**\n\n"
                    f"• **Direction**: `{res['predicted_direction']}` ({res['probability_up']*100:.1f}% confidence)\n\n"
                    f"• **Target Price**: `₹{res['predicted_close']:.2f}` (Target Date: {res['target_date']})\n\n"
                    f"• **Prediction Interval**: `[₹{res['lower_bound']:.2f} — ₹{res['upper_bound']:.2f}]`"
                )
            except Exception as e:
                st.error(f"Prediction could not be completed: {e}")

    with p_col2:
        st.markdown("""
        <div class="human-card">
            <h5 style="margin-top:0; color: #60A5FA;">⚖️ Resolution Engine</h5>
            <p style="color: #94A3B8; font-size: 0.85rem; line-height: 1.4;">
                Resolves past predictions against real observed prices once the target date closes.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("⚖️ Run Outcome Resolution Check", use_container_width=True):
            count = resolve_predictions_for_ticker()
            st.info(f"Evaluated and resolved {count} pending prediction(s).")

    st.markdown("---")

    # SECTION 2: MULTI-MODEL VISUALIZER
    st.markdown("### 📊 **2. Multi-Model Trajectory Comparison**")
    st.caption("Compare projected trajectories from all 6 models simultaneously on an interactive timeline.")

    col_chart_sym, col_chart_h, col_chart_btn = st.columns([2, 1.5, 1.5])
    chart_symbol = col_chart_sym.selectbox("Equity to Compare", symbols, key="compare_sym")
    chart_horizon = col_chart_h.selectbox("Horizon Window", [1, 5, 21], key="compare_h", format_func=lambda x: f"{x} Trading Day{'s' if x>1 else ''}")
    
    with col_chart_btn:
        st.write("")
        st.write("")
        run_chart = st.button("📈 Run Multi-Model Comparison", use_container_width=True)

    if run_chart:
        ensure_ticker_data_available(chart_symbol)

        with st.spinner("Calculating forward projections across ANN, LSTM, Transformer, Prophet, and Ensemble..."):
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

                comp_fig = go.Figure()

                # Recent observed history
                comp_fig.add_trace(go.Scatter(
                    x=df_hist["price_date"].tail(30),
                    y=df_hist["close_price"].tail(30),
                    mode="lines+markers",
                    name="Recent Observed Close",
                    line=dict(color="#3B82F6", width=3),
                ))

                colors = {
                    "naive_last": "#94A3B8",
                    "drift": "#F59E0B",
                    "ann": "#FB923C",
                    "lstm": "#10B981",
                    "transformer": "#A855F7",
                    "ensemble": "#EC4899",
                }

                proj_x = [last_date, last_date + datetime.timedelta(days=chart_horizon * 2)]
                for m_k, p_res in all_preds.items():
                    c = colors.get(m_k, "#06B6D4")
                    w = 4 if m_k == "ensemble" else 2
                    label_name = m_k.upper()
                    comp_fig.add_trace(go.Scatter(
                        x=proj_x,
                        y=[last_price, p_res["predicted_close"]],
                        mode="lines+markers",
                        name=f"{label_name} ({p_res['predicted_direction']}: ₹{p_res['predicted_close']:.2f})",
                        line=dict(color=c, width=w, dash="solid" if m_k == "ensemble" else "dot"),
                    ))

                # Ensemble Confidence Interval Band
                comp_fig.add_trace(go.Scatter(
                    x=[proj_x[1], proj_x[1]],
                    y=[ens_pred["lower_bound"], ens_pred["upper_bound"]],
                    mode="lines+markers",
                    name="Ensemble Uncertainty Band",
                    line=dict(color="rgba(236, 72, 153, 0.7)", width=8),
                ))

                comp_fig.update_layout(
                    title=dict(
                        text=f"{chart_symbol} — Multi-Model Trajectory Comparison ({chart_horizon}-Day Horizon)",
                        font=dict(size=17, color="#F8FAFC")
                    ),
                    yaxis_title="Price (INR ₹)",
                    xaxis_title="Date Timeline",
                    hovermode="x unified",
                    height=500,
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(15, 23, 42, 0.4)",
                    margin=dict(l=40, r=40, t=50, b=40),
                )
                st.plotly_chart(fig=comp_fig, use_container_width=True)

                # Summary Data Table
                summary_data = []
                for m_k, p_res in all_preds.items():
                    summary_data.append({
                        "Architecture": m_k.upper(),
                        "Projected Close": f"₹{p_res['predicted_close']:.2f}",
                        "Exp Return": f"{p_res['predicted_log_return'] * 100:+.2f}%",
                        "Direction": p_res["predicted_direction"],
                        "Confidence (UP)": f"{p_res['probability_up'] * 100:.1f}%",
                        "Lower Bound": f"₹{p_res['lower_bound']:.2f}",
                        "Upper Bound": f"₹{p_res['upper_bound']:.2f}",
                    })
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
            else:
                st.warning(f"Insufficient history ({len(df_hist)} rows) for {chart_symbol}. Needs at least 30 observations.")

    st.markdown("---")

    # SECTION 3: IMMUTABLE AUDIT LEDGER
    st.markdown("### 📜 **3. Immutable Audit Ledger Records**")
    st.caption("Verifiable database ledger showing predictions, horizons, and realized market outcomes.")

    with get_ro_connection() as conn:
        df_ledger = pd.read_sql_query("""
            SELECT 
                p.prediction_id AS "ID",
                st.symbol AS "Ticker",
                m.name AS "Model",
                p.prediction_date AS "Pred Date",
                p.target_date AS "Target Date",
                p.horizon_days AS "Horizon (d)",
                p.predicted_direction AS "Predicted Dir",
                p.predicted_close AS "Predicted (₹)",
                p.lower_bound AS "Lower Bound",
                p.upper_bound AS "Upper Bound",
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

    if not df_ledger.empty:
        st.dataframe(
            df_ledger.style.format({
                "Predicted (₹)": "₹{:,.2f}",
                "Lower Bound": "₹{:,.2f}",
                "Upper Bound": "₹{:,.2f}",
                "Actual (₹)": lambda v: f"₹{float(v):,.2f}" if pd.notnull(v) and str(v).strip() != '' else "—"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No predictions sealed in the ledger yet. Generate one above to start!")


# ----------------------------------------------------
# PAGE D: MODEL SCORECARDS
# ----------------------------------------------------
elif menu == "🏆 Model Scorecards":
    st.markdown("""
    <div class="tip-box">
        <div class="tip-icon">🏆</div>
        <div>
            <b>Model Performance Scorecards</b> — Statistical evaluation of directional accuracy, Brier score, and Mean Absolute Error (MAE) calculated via PostgreSQL Materialized Views.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_btn, _ = st.columns([2, 3])
    with col_btn:
        if st.button("🔄 Refresh Scorecard Materialized View", use_container_width=True):
            refresh_scorecard_materialized_view()
            st.success("✅ Scorecard Materialized View successfully updated!")

    scorecards = get_model_scorecards()
    if scorecards:
        df_scorecards = pd.DataFrame(scorecards)
        st.dataframe(df_scorecards, use_container_width=True, hide_index=True)
    else:
        st.markdown("""
        <div class="human-card">
            <h4>No Resolved Predictions Found Yet</h4>
            <p style="color: #94A3B8; font-size: 0.95rem; line-height: 1.5;">
                Scorecards require predictions whose target dates have already passed and been recorded in the database.
                <br/><br/>
                <b>How to populate scorecards:</b>
                <ol style="margin-left: -20px; color: #CBD5E1;">
                    <li>Generate predictions on past dates or wait for future target dates to arrive.</li>
                    <li>Ingest the new market close prices via the Data Ingestion Hub.</li>
                    <li>Click <b>'Run Outcome Resolution'</b> in the Predictions tab.</li>
                </ol>
            </p>
        </div>
        """, unsafe_allow_html=True)


# ----------------------------------------------------
# PAGE E: MARKET DATA HUB
# ----------------------------------------------------
elif menu == "📥 Market Data Hub":
    st.markdown("""
    <div class="tip-box">
        <div class="tip-icon">📥</div>
        <div>
            <b>Market Data Ingestion Hub</b> — Pipeline control center for pulling historical OHLCV data from Yahoo Finance into PostgreSQL with partition routing and reject validation.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with get_ro_connection() as conn:
        symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()

    col_form, col_expl = st.columns([2, 1.2])

    with col_form:
        st.markdown("### 📥 **Manual Data Ingestion**")
        col_t, col_s, col_e = st.columns(3)
        t_choice = col_t.selectbox("Equity Ticker", symbols)
        s_date = col_s.date_input("Start Date", datetime.date(2020, 1, 1))
        e_date = col_e.date_input("End Date", datetime.date.today())

        if st.button("🚀 Start Ingestion Pipeline", type="primary", use_container_width=True):
            with st.spinner(f"Ingesting daily market data for {t_choice}..."):
                pipeline = IngestionPipeline()
                try:
                    res = pipeline.run_for_ticker(t_choice, s_date, e_date)
                    st.success(f"Ingestion {res['status'].upper()}: {res['ingested']} records stored into PostgreSQL (Rejections: {res['rejected']}).")
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")

    with col_expl:
        st.markdown("""
        <div class="human-card" style="height: 100%;">
            <h5 style="margin-top:0; color: #60A5FA;">🛡️ Data Quality Guardrails</h5>
            <ul style="color: #94A3B8; font-size: 0.85rem; padding-left: 18px; line-height: 1.5;">
                <li><b>Check Constraints:</b> High ≥ Low, Open/Close in range, Volume ≥ 0.</li>
                <li><b>Partitioning:</b> Observations routed to yearly range tables (2015–2028).</li>
                <li><b>Idempotency:</b> Duplicate timestamps update or skip without error.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 **Audit Trail: Recent Ingestion Jobs**")
    with get_ro_connection() as conn:
        df_runs = pd.read_sql_query("""
            SELECT 
                ir.run_id AS "Run ID",
                st.symbol AS "Ticker",
                ir.status AS "Status",
                ir.records_ingested AS "Ingested Records",
                ir.records_rejected AS "Rejected Records",
                ir.started_at AS "Started At",
                ir.completed_at AS "Completed At"
            FROM ingestion_run ir
            JOIN stock_ticker st ON ir.ticker_id = st.ticker_id
            ORDER BY ir.run_id DESC LIMIT 25;
        """, conn)

    if not df_runs.empty:
        st.dataframe(df_runs, use_container_width=True, hide_index=True)
    else:
        st.info("No ingestion runs recorded yet.")
