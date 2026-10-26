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
    page_title="STOCK&PREDICT",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for cards, banners, and modal containers
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .auth-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 14px;
        padding: 24px;
        margin-top: 15px;
        margin-bottom: 25px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.25);
    }
    .section-banner {
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 18px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .banner-info {
        background: rgba(33, 150, 243, 0.12);
        border-left: 4px solid #2196F3;
        color: #90caf9;
    }
    .banner-warning {
        background: rgba(255, 152, 0, 0.12);
        border-left: 4px solid #FF9800;
        color: #ffcc80;
    }
    .banner-success {
        background: rgba(76, 175, 80, 0.12);
        border-left: 4px solid #4CAF50;
        color: #a5d6a7;
    }
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .badge-auto { background: rgba(76, 175, 80, 0.2); color: #81c784; border: 1px solid #81c784; }
    .badge-manual { background: rgba(33, 150, 243, 0.2); color: #64b5f6; border: 1px solid #64b5f6; }
    .badge-locked { background: rgba(244, 67, 54, 0.2); color: #ef9a9a; border: 1px solid #ef9a9a; }
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
                    return False, "User not found."
                pw_hash, role, is_active = row
                if not is_active:
                    return False, "Account is disabled."
                try:
                    ph.verify(pw_hash, password)
                    return True, role
                except VerifyMismatchError:
                    return False, "Incorrect password."
    except Exception as e:
        # Fallback check for demo credentials
        if username.lower() == "admin" and password == "admin":
            return True, "admin"
        return False, str(e)


def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    """Registers a new user into PostgreSQL app_user table."""
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
        return True, "Account registered successfully! You can now log in."
    except Exception as e:
        err_msg = str(e)
        if "unique" in err_msg.lower():
            return False, "Username or email already exists."
        return False, err_msg


# App Header
st.title("📈 STOCK&PREDICT")
st.markdown("##### *Institutional-Grade Quantitative Forecasting & Model Accountability Ledger*")

# ----------------------------------------------------
# SIDEBAR CONTROLS
# ----------------------------------------------------
st.sidebar.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
st.sidebar.title("Navigation")

# Dynamic Menu options based on Authentication
if st.session_state.authenticated:
    st.sidebar.success(f"👤 Logged in as: **{st.session_state.user_name}** ({st.session_state.user_role.upper()})")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_name = None
        st.session_state.user_role = "guest"
        st.rerun()

    menu = st.sidebar.radio(
        "Explore Platform",
        ["Dashboard", "Stock Explorer", "Predictions & Forecasting", "Model Scorecards", "Data Ingestion Hub"],
        index=0,
    )

    st.sidebar.divider()
    st.sidebar.markdown("### 💡 Ingestion Workflow")
    st.sidebar.info(
        "• **10 Active Stocks**: Core stocks (`RELIANCE`, `TCS`, `INFY`, `ITC`, etc.) have 4 years of stored daily OHLCV.\n\n"
        "• **Auto-Fetch**: If you select any stock without local prices, the app will **auto-ingest** from Yahoo Finance.\n\n"
        "• **Manual Ingestion**: Optional backfill via the Data Ingestion Hub."
    )
else:
    st.sidebar.warning("🔒 **Guest Access (Restricted)**\n\nOnly the 10 market stocks are visible. Please log in or sign up to unlock AI predictions, scorecards, and data ingestion.")
    menu = "Dashboard (Guest)"


# ----------------------------------------------------
# VIEW 1: GUEST MODE (ONLY 10 CURRENT STOCKS & LOGIN/SIGNUP)
# ----------------------------------------------------
if not st.session_state.authenticated:
    st.markdown("""
    <div class="section-banner banner-warning">
        🔒 <b>Guest Mode Active</b> — Only the 10 current market stock prices are displayed. Log in with demo credentials (<b>Username:</b> <code>Admin</code> | <b>Password:</b> <code>admin</code>) or Sign Up to unlock <b>Stock Explorer, ANN, LSTM, Transformer, Ensemble Forecasting, and Ingestion Hub</b>.
    </div>
    """, unsafe_allow_html=True)

    # Auth Tabs: Login and Signup
    with st.container():
        tab_login, tab_signup = st.tabs(["🔑 Login with Credentials", "📝 Create Demo Account (Sign Up)"])

        with tab_login:
            st.markdown("""
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 18px; margin-bottom: 20px;">
                <h4 style="margin-top:0;">Demo Admin Credentials</h4>
                <p style="margin-bottom: 0; color: #bbb;">Use <b>Username:</b> <code style="color: #64b5f6; font-size:1.1rem;">Admin</code> &nbsp;|&nbsp; <b>Password:</b> <code style="color: #81c784; font-size:1.1rem;">admin</code> to gain full access.</p>
            </div>
            """, unsafe_allow_html=True)

            col_l1, col_l2 = st.columns(2)
            login_user = col_l1.text_input("Username", value="Admin", key="login_u")
            login_pass = col_l2.text_input("Password", type="password", value="admin", key="login_p")

            if st.button("🚀 Log In to Unlock All Features", type="primary", use_container_width=True):
                is_valid, role_or_err = verify_login(login_user, login_pass)
                if is_valid:
                    st.session_state.authenticated = True
                    st.session_state.user_name = login_user
                    st.session_state.user_role = role_or_err
                    st.toast(f"Welcome, {login_user}! All features unlocked.", icon="🎉")
                    st.rerun()
                else:
                    st.error(f"Authentication failed: {role_or_err}")

        with tab_signup:
            st.markdown("##### Create a new user account in PostgreSQL")
            col_s1, col_s2, col_s3 = st.columns(3)
            signup_user = col_s1.text_input("Choose Username", key="sign_u")
            signup_email = col_s2.text_input("Email Address", key="sign_e")
            signup_pass = col_s3.text_input("Password", type="password", key="sign_p")

            if st.button("✨ Create Account", use_container_width=True):
                ok, msg = register_user(signup_user, signup_email, signup_pass)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    st.markdown("---")

    # Display 10 current data stocks (Available to all guests)
    st.subheader("📊 10 Representative Indian Market Equities (PostgreSQL Partitioned Store)")
    with get_ro_connection() as conn:
        df_10_stocks = pd.read_sql_query("""
            SELECT DISTINCT ON (st.symbol)
                st.symbol AS "Ticker Symbol",
                st.name AS "Company Name",
                st.exchange AS "Exchange",
                ind.name AS "Industry Sector",
                sp.price_date AS "Latest Observation",
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
        st.dataframe(df_10_stocks, use_container_width=True, hide_index=True)
    else:
        st.info("No prices ingested yet.")

    # Locked Features Preview Card
    st.markdown("""
    <div class="metric-card" style="margin-top: 25px;">
        <h4 style="margin-top:0;">🔒 Advanced Features Locked (Requires Login)</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 10px;">
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>Deep Neural Networks</b> <span class="badge badge-locked">Locked</span><br/>
                <small style="color: #aaa;">Artificial Neural Networks (ANN) & LSTM Recurrent sequence models.</small>
            </div>
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>Transformer Self-Attention</b> <span class="badge badge-locked">Locked</span><br/>
                <small style="color: #aaa;">Multi-Head Temporal Attention network for direction classification.</small>
            </div>
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>Consensus Ensemble</b> <span class="badge badge-locked">Locked</span><br/>
                <small style="color: #aaa;">Interactive Plotly charts comparing 5 model projections and bounds.</small>
            </div>
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>Immutable Audit Ledger</b> <span class="badge badge-locked">Locked</span><br/>
                <small style="color: #aaa;">Trigger-protected ledger with automated outcome evaluation.</small>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ----------------------------------------------------
# AUTHENTICATED ACCESS: FULL APPLICATION FEATURES
# ----------------------------------------------------

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

    # Auto-ingest if below threshold
    with st.spinner(f"⚡ Auto-Ingesting historical market data for {symbol} ({exchange}) from Yahoo Finance..."):
        try:
            pipeline = IngestionPipeline()
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=years * 365)
            res = pipeline.run_for_ticker(symbol, start_date, end_date, exchange)
            if res["ingested"] > 0:
                st.toast(f"✅ Auto-ingested {res['ingested']} records for {symbol} into PostgreSQL!", icon="📥")
                return True
        except Exception as e:
            st.error(f"Auto-ingestion failed for {symbol}: {e}")
            return False
    return False


# ----------------------------------------------------
# PAGE A: DASHBOARD
# ----------------------------------------------------
if menu == "Dashboard":
    st.markdown('<div class="section-banner banner-success"><b>Authorized Access</b> — Real-time telemetry on PostgreSQL connection pool and market data repository.</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    db_ok = check_db_health()
    col1.metric("Database Engine", "PostgreSQL 16/18" if db_ok else "OFFLINE", "Online" if db_ok else "Error")

    with get_ro_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stock_ticker WHERE is_active = TRUE;")
            active_tickers = cur.fetchone()[0]
            col2.metric("Active Equities", active_tickers, "NSE / BSE")

            cur.execute("SELECT COUNT(*) FROM stock_price;")
            total_prices = cur.fetchone()[0]
            col3.metric("Persisted Prices", f"{total_prices:,}", "Partitioned")

            cur.execute("SELECT COUNT(*) FROM prediction;")
            total_preds = cur.fetchone()[0]
            col4.metric("Sealed Predictions", total_preds, "Immutable")

    st.markdown("---")
    
    # Workflow highlights card
    st.markdown("""
    <div class="metric-card">
        <h4 style="margin-top:0;">🚀 Quick Operational Workflow</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-top: 10px;">
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>1. Market Ingestion</b> <span class="badge badge-auto">Auto / Manual</span><br/>
                <small style="color: #bbb;">Historical OHLCV is fetched via yfinance, validated against OHLC bounds, and range-partitioned in PostgreSQL.</small>
            </div>
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>2. Model Forecasting</b> <span class="badge badge-manual">5 AI Models</span><br/>
                <small style="color: #bbb;">Generates forecasts (ANN, LSTM, Transformer, Prophet, Ensemble) with zero look-ahead bias.</small>
            </div>
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>3. Immutable Ledger</b> <span class="badge badge-auto">Database Enforced</span><br/>
                <small style="color: #bbb;">Predictions cannot be edited or deleted (blocked by DB triggers & REVOKE policies).</small>
            </div>
            <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <b>4. Automatic Resolution</b> <span class="badge badge-auto">Realized Outcomes</span><br/>
                <small style="color: #bbb;">Grades predictions automatically once actual market closes are recorded.</small>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("📊 Latest Market Observations in PostgreSQL")
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
        st.dataframe(df_latest, use_container_width=True, hide_index=True)
    else:
        st.warning("No price data found in PostgreSQL yet.")


# ----------------------------------------------------
# PAGE B: STOCK EXPLORER
# ----------------------------------------------------
elif menu == "Stock Explorer":
    st.markdown('<div class="section-banner banner-info"><b>Interactive Stock Explorer</b> — Inspect historical OHLCV candlestick charts and underlying database observations.</div>', unsafe_allow_html=True)

    with get_ro_connection() as conn:
        df_tickers = pd.read_sql_query("SELECT symbol, name, exchange FROM stock_ticker ORDER BY symbol;", conn)

    col_sym, col_action = st.columns([3, 1])
    selected_symbol = col_sym.selectbox("Select Stock Ticker", df_tickers["symbol"].tolist())
    ticker_info = df_tickers[df_tickers["symbol"] == selected_symbol].iloc[0]

    with col_action:
        st.write("")
        st.write("")
        if st.button("🔄 Sync / Re-Ingest Ticker", use_container_width=True):
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
        c_m2.metric("Date Range", f"{df_prices.iloc[0]['price_date']} to {latest_row['price_date']}")
        c_m3.metric("Stored Observations", f"{len(df_prices):,} days")
        pct_change = ((float(latest_row['close_price']) - float(df_prices.iloc[-2]['close_price'])) / float(df_prices.iloc[-2]['close_price']) * 100) if len(df_prices) > 1 else 0
        c_m4.metric("Last Day Change", f"{pct_change:+.2f}%")

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
            height=480,
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📄 View Stored Historical Price Table (Latest 50 Observations)"):
            st.dataframe(df_prices.tail(50), use_container_width=True, hide_index=True)
    else:
        st.warning(f"No price history in PostgreSQL for {selected_symbol}. Click 'Sync / Re-Ingest Ticker' above to fetch it.")


# ----------------------------------------------------
# PAGE C: PREDICTIONS & FORECASTING
# ----------------------------------------------------
elif menu == "Predictions & Forecasting":
    st.markdown('<div class="section-banner banner-info"><b>AI Forecasting & Ledger</b> — Execute Neural Networks (ANN, LSTM, Transformer, Prophet, Ensemble) and record tamper-proof predictions.</div>', unsafe_allow_html=True)

    with get_ro_connection() as conn:
        symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()
        models = pd.read_sql_query("SELECT name FROM model ORDER BY name;", conn)["name"].tolist()

    # Section 1: Single Prediction Card
    st.markdown("""
    <div class="metric-card">
        <h4 style="margin: 0 0 10px 0;">⚡ 1. Generate & Seal Immutable Prediction</h4>
        <small style="color: #aaa;">Generates an algorithmic forecast up to the cutoff date with zero look-ahead bias, permanently storing it in PostgreSQL.</small>
    </div>
    """, unsafe_allow_html=True)

    p_col1, p_col2 = st.columns([2.5, 1.5])
    with p_col1:
        c1, c2, c3 = st.columns(3)
        t_sym = c1.selectbox("Equity Ticker", symbols, index=0)
        m_name = c2.selectbox("Model Architecture", models, index=min(len(models)-1, 3))
        h_days = c3.selectbox("Horizon", [1, 5, 21], format_func=lambda x: f"{x} Trading Day{'s' if x>1 else ''}")

        if st.button("🔮 Generate & Seal Forecast", use_container_width=True, type="primary"):
            ensure_ticker_data_available(t_sym)
            try:
                res = generate_and_persist_prediction(t_sym, m_name, datetime.date.today(), horizon_days=h_days)
                st.success(
                    f"✅ Prediction Sealed in DB Ledger! (ID: #{res['prediction_id']})\n\n"
                    f"• **Direction**: {res['predicted_direction']} ({res['probability_up']*100:.1f}% confidence)\n"
                    f"• **Target Price**: ₹{res['predicted_close']:.2f} (Target Date: {res['target_date']})\n"
                    f"• **Prediction Interval**: [₹{res['lower_bound']:.2f} - ₹{res['upper_bound']:.2f}]"
                )
            except Exception as e:
                st.error(f"Prediction failed: {e}")

    with p_col2:
        st.markdown("**Outcome Resolution Engine**")
        st.caption("Resolves sealed predictions against target date closing prices as they arrive.")
        if st.button("⚖️ Run Outcome Resolution", use_container_width=True):
            count = resolve_predictions_for_ticker()
            st.info(f"Resolved {count} pending predictions.")

    st.markdown("---")

    # Section 2: Multi-Model & Ensemble Visualizer
    st.markdown("""
    <div class="metric-card">
        <h4 style="margin: 0 0 10px 0;">📊 2. Multi-Model & Ensemble Visualizer</h4>
        <small style="color: #aaa;">Compare projected trajectories from ANN, LSTM, Transformer, Prophet, and Consensus Ensemble side-by-side.</small>
    </div>
    """, unsafe_allow_html=True)

    col_chart_sym, col_chart_h, col_chart_btn = st.columns([2, 1.5, 1.5])
    chart_symbol = col_chart_sym.selectbox("Compare Forecasts For Symbol", symbols, key="compare_sym")
    chart_horizon = col_chart_h.selectbox("Forecast Horizon", [1, 5, 21], key="compare_h", format_func=lambda x: f"{x} Day{'s' if x>1 else ''}")
    
    with col_chart_btn:
        st.write("")
        st.write("")
        run_chart = st.button("📈 Run Multi-Model Comparison", use_container_width=True)

    if run_chart:
        ensure_ticker_data_available(chart_symbol)

        with st.spinner("Executing models (ANN, LSTM, Transformer, Prophet, Ensemble)..."):
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
                    line=dict(color="#1f77b4", width=3),
                ))

                colors = {
                    "naive_last": "#9e9e9e",
                    "drift": "#ffb74d",
                    "ann": "#ff7043",
                    "lstm": "#66bb6a",
                    "transformer": "#ab47bc",
                    "ensemble": "#ef5350",
                }

                proj_x = [last_date, last_date + datetime.timedelta(days=chart_horizon * 2)]
                for m_k, p_res in all_preds.items():
                    c = colors.get(m_k, "#26c6da")
                    w = 4 if m_k == "ensemble" else 2
                    comp_fig.add_trace(go.Scatter(
                        x=proj_x,
                        y=[last_price, p_res["predicted_close"]],
                        mode="lines+markers",
                        name=f"{m_k.upper()} ({p_res['predicted_direction']}: ₹{p_res['predicted_close']:.2f})",
                        line=dict(color=c, width=w, dash="solid" if m_k == "ensemble" else "dot"),
                    ))

                # Ensemble Confidence Interval Band
                comp_fig.add_trace(go.Scatter(
                    x=[proj_x[1], proj_x[1]],
                    y=[ens_pred["lower_bound"], ens_pred["upper_bound"]],
                    mode="lines+markers",
                    name="Ensemble Bounds [Min, Max]",
                    line=dict(color="rgba(239, 83, 80, 0.6)", width=8),
                ))

                comp_fig.update_layout(
                    title=f"{chart_symbol} — Multi-Model Trajectory Comparison ({chart_horizon}-Day Horizon)",
                    yaxis_title="Price (INR)",
                    xaxis_title="Timeline",
                    hovermode="x unified",
                    height=500,
                    template="plotly_dark",
                )
                st.plotly_chart(fig=comp_fig, use_container_width=True)

                # Metrics Table
                summary_data = []
                for m_k, p_res in all_preds.items():
                    summary_data.append({
                        "Model Architecture": m_k.upper(),
                        "Predicted Close": f"₹{p_res['predicted_close']:.2f}",
                        "Expected Return": f"{p_res['predicted_log_return'] * 100:+.3f}%",
                        "Direction": p_res["predicted_direction"],
                        "Probability UP": f"{p_res['probability_up'] * 100:.1f}%",
                        "Lower Bound": f"₹{p_res['lower_bound']:.2f}",
                        "Upper Bound": f"₹{p_res['upper_bound']:.2f}",
                    })
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
            else:
                st.warning(f"Insufficient historical data ({len(df_hist)} rows) for {chart_symbol}. Needs at least 30 observations.")

    st.markdown("---")

    # Section 3: Ledger Table
    st.markdown("""
    <div class="metric-card">
        <h4 style="margin: 0 0 10px 0;">📜 3. Sealed Predictions Ledger Records</h4>
        <small style="color: #aaa;">Immutable database records with audit timestamps and realized outcomes.</small>
    </div>
    """, unsafe_allow_html=True)

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
        st.dataframe(df_ledger, use_container_width=True, hide_index=True)
    else:
        st.info("No predictions sealed in the ledger yet.")


# ----------------------------------------------------
# PAGE D: MODEL SCORECARDS
# ----------------------------------------------------
elif menu == "Model Scorecards":
    st.markdown('<div class="section-banner banner-info"><b>Model Performance Scorecards</b> — Graded statistical performance evaluated strictly against identical baseline samples.</div>', unsafe_allow_html=True)

    col_btn, _ = st.columns([2, 3])
    with col_btn:
        if st.button("🔄 Refresh Scorecard Materialized View", use_container_width=True):
            refresh_scorecard_materialized_view()
            st.success("Materialized view refreshed!")

    scorecards = get_model_scorecards()
    if scorecards:
        df_scorecards = pd.DataFrame(scorecards)
        st.dataframe(df_scorecards, use_container_width=True, hide_index=True)
    else:
        st.info("No resolved predictions available for scorecards yet. Generate predictions and resolve them once market data arrives.")


# ----------------------------------------------------
# PAGE E: DATA INGESTION HUB
# ----------------------------------------------------
elif menu == "Data Ingestion Hub":
    st.markdown("""
    <div class="section-banner banner-info">
        <b>Market Data Ingestion Hub</b> — Fetch, validate, and partition daily stock OHLCV data from Yahoo Finance into PostgreSQL.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="metric-card">
        <h4 style="margin-top:0;">ℹ️ How Ingestion Works: Automatic vs. Manual</h4>
        <p style="color: #ccc; margin-bottom: 5px;">
            <b>• Automatic Ingestion:</b> When you request a prediction for a stock that hasn't been cached yet, the application automatically fetches and persists its historical OHLCV data into PostgreSQL.
        </p>
        <p style="color: #ccc; margin-bottom: 0;">
            <b>• Manual Ingestion:</b> Use this control to backfill specific date ranges, refresh recent prices, or inspect ingestion reject logs.
        </p>
    </div>
    """, unsafe_allow_html=True)

    with get_ro_connection() as conn:
        symbols = pd.read_sql_query("SELECT symbol FROM stock_ticker ORDER BY symbol;", conn)["symbol"].tolist()

    st.markdown("### 📥 Manual Ingestion Form")
    col_t, col_s, col_e = st.columns(3)
    t_choice = col_t.selectbox("Select Symbol to Ingest", symbols)
    s_date = col_s.date_input("Start Date", datetime.date(2020, 1, 1))
    e_date = col_e.date_input("End Date", datetime.date.today())

    if st.button("🚀 Trigger Ingestion Job", type="primary", use_container_width=True):
        with st.spinner(f"Ingesting {t_choice} from Yahoo Finance..."):
            pipeline = IngestionPipeline()
            try:
                res = pipeline.run_for_ticker(t_choice, s_date, e_date)
                st.success(f"Ingestion {res['status']}: {res['ingested']} observations stored into PostgreSQL (Rejects: {res['rejected']}).")
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

    st.markdown("---")
    st.markdown("### 📋 Audit Trail: Recent Ingestion Runs")
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
        st.info("No ingestion runs recorded yet.")
