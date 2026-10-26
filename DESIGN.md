# Design System: StockPredict Modern Financial Analytics

## 1. Design Direction & Philosophy
- **Identity**: Modern, clean, high-clarity Institutional Financial Web App.
- **Tone**: Sophisticated, professional, accessible, authoritative (clean contrast, no cramped terminal aesthetic, no AI slop).
- **Core Principle**: Clear visual hierarchy, generous legible typography, prominent interactive buttons, intuitive hamburger menu, and a comprehensive public landing page showcasing all services with clear calls-to-action.

## 2. Color Palette (Tokens)
- **Background Deep Canvas**: `#0D1117`
- **Surface Elevation 1 (Card / Container)**: `#161B22`
- **Surface Elevation 2 (Hover / Active)**: `#21262D`
- **Border Subtle**: `#30363D`
- **Primary Accent (Brand Brand Gold / Amber)**: `#F59E0B`
- **Primary Accent Hover**: `#D97706`
- **Text High-Emphasis (Headings, Values)**: `#F0F6FC`
- **Text Mid-Emphasis (Labels, Body)**: `#C9D1D9`
- **Text Muted (Captions, Timestamps)**: `#8B949E`
- **Bullish Green**: `#2EA043` / `#3FB950`
- **Bearish Red**: `#DA3633` / `#F85149`
- **Blue Informational**: `#58A6FF`

## 3. Typography
- **Headings & Primary UI**: `'Inter', -apple-system, BlinkMacSystemFont, sans-serif`
- **Financial Numbers & Ticker Codes**: `'JetBrains Mono', 'Roboto Mono', monospace` with `font-variant-numeric: tabular-nums`
- **Scale**:
  - Hero Display: `2.4rem` / `700 weight`
  - Section Title: `1.4rem` / `600 weight`
  - Body Text: `15px` / `1.6 line-height`
  - Financial Data / Metric Value: `1.8rem` / `700 weight`
  - Field Labels & Badges: `13px` / `600 weight`

## 4. Components & Affordances
- **Real Clickable Buttons**: Raised borders, clear hover transitions, standard minimum `42px` touch targets, distinct primary (filled) and secondary (outlined) states.
- **Navigation**:
  - Public: Top Header Bar with live Nifty/Sensex ticker, platform status, and a prominent "Login to Terminal" action.
  - Authenticated: Integrated hamburger / top drawer navigation menu to switch between Market Overview, Interactive Charts, AI Forecasting, Immutable Ledger, and Data Ingestion Hub.
- **Landing Page Structure**:
  - Header & Ticker Bar: Real-time price metrics across Indian indices and equities.
  - Platform Hero: Clear value proposition without marketing fluff.
  - Service Capabilities Grid: 4 core service cards (Predictive AI Models, Immutable DB Ledger, Level-2 Orderbook Depth, Real-Time Data Ingestion), each with a direct "Access Service" login button.
  - Live Market Data Table: Top 10 Indian equities with clean pagination and standard column alignments.
  - Dedicated Authentication Portal: Clean, modern card with tabs for Login and Sign Up.

