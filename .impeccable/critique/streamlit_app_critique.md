# Impeccable Critique Synthesis Report: `streamlit_app.py`

**Target**: `streamlit_app.py`  
**Profile**: Institutional Quantitative Terminal (Indian Equities — NSE/BSE)  
**Standard**: Bloomberg Terminal / Refinitiv Eikon Architecture  
**Assessment Provenance**: Two isolated parallel subagents (Assessment A: Design Review | Assessment B: Detector Evidence via CLI)

---

## 1. Executive Summary & Verdict

### Verdict: **High-Risk Category Mismatch (Consumer AI Slop vs. Institutional Terminal)**
The existing interface exhibits classic consumer AI SaaS tropes: a multi-colored gradient hero banner, conversational copy ("👋 Welcome to StockPredict", "✨ Create a New Demo Account"), 18px rounded pill borders, and an unauthenticated paywall (`st.stop()`) that locks the user out of the app.

To deliver on the requirements in `PRODUCT.md` and satisfy the user's explicit request for a **Bloomberg Terminal-grade experience**, the interface must be completely transformed into a high-density, multi-pane quantitative workstation featuring amber/cyan on obsidian slate, top command bar, continuous market ticker tape, Level-2 orderbook depth, execution telemetry, and a catalyst news stream.

---

## 2. Assessment B: Detector Evidence (Deterministic Scan)

The bundled Impeccable detector (`.agent/skills/impeccable/scripts/impeccable detect --json streamlit_app.py`) identified **6 anti-patterns** belonging to the `slop` category:

1. **`side-tab` (4 occurrences)**: Lines 441, 445, 449, 453 — Colored 3px left border accents on cards (`border-left: 3px solid #60A5FA`, etc.). This is a primary tell of AI-generated consumer landing templates.
2. **`overused-font` (2 occurrences)**: Lines 31, 34 — Injection of Google Fonts `Plus Jakarta Sans`. Overused on boilerplate sites, lacking the typographic authority of an institutional monospace terminal font.

---

## 3. Assessment A: Design Review & Nielsen Heuristics

- **Information Density**: Severely constrained by a narrow `max-width: 1300px` container, large 3rem margins, and single-column vertical scrolling.
- **Top Navigation**: None. Relies on the default Streamlit vertical sidebar, taking up 300px of valuable horizontal space needed for charts and multi-pane analysis.
- **Microstructure Telemetry**: No orderbook depth, no bid-ask spread indicators, no execution slippage estimation, and no catalyst stream.
- **Heuristic Score**: **21 / 40** (Sub-institutional). Fails Visibility of System Status (cosmetic telemetry pills) and Aesthetic / Minimalist Design (excessive marketing prose).

---

## 4. Architectural Transformation Plan

We will overhaul `streamlit_app.py` into a genuine Bloomberg Terminal:
1. **Terminal Command Header & Indian Market Ticker Tape**: Full-width header with brand indicator, active Indian equity ticker tape (`NIFTY 50`, `SENSEX`, `RELIANCE`, `TCS`, `INFY`, `ITC`, etc.) with real-time percentage deltas, and live PostgreSQL connection pool telemetry.
2. **Horizontal Navbar Tabs**: Replace sidebar with a top institutional tab bar (`[1: MARKET MONITOR]`, `[2: TERMINAL WORKSTATION]`, `[3: AI CONSENSUS MATRIX]`, `[4: IMMUTABLE LEDGER]`, `[5: INGESTION HUB]`).
3. **Multi-Pane Workspace Layout**:
   - **Left Pane (60%)**: Candlestick charts with technical overlays (EMA-20, EMA-50, VWAP) and multi-model projection trajectory cones.
   - **Top Right Pane (40%)**: Level-2 Orderbook Ladder (Bid/Ask depth with visual bars, spread in bps).
   - **Bottom Right Pane (40%)**: Trade execution telemetry (Slippage estimate, Liquidity score, Real-time volatility).
4. **Market News & Catalyst Feed**: Corporate earnings dates, RBI announcements, and sentiment indicators linked to the active stock.
5. **Obsidian & Amber/Cyan Terminal Aesthetic**: Monospace typography (`JetBrains Mono`, `Roboto Mono`, `tabular-nums`), 2px border radiuses, dark slate `#080B10` background, and elimination of all side-tab borders and gradient slop.
6. **Unrestricted Guest Terminal Mode**: Guests immediately see the live terminal in read-only observation mode with simulated orders and real price feeds; authentication is an unobtrusive top-right terminal operator toggle.
