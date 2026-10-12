# STOCK&PREDICT

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](https://github.com/atanu-sarkar/stock-predict-app)
[![Python](https://img.shields.io/badge/python-3.11-brightgreen)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-16-blue)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-AGPL--3.0--only-orange)](LICENSE)

An institutional-grade stock direction prediction and model accountability platform for Indian equities (NSE/BSE). Every prediction is permanently sealed in an immutable PostgreSQL ledger, evaluated against real market observations without look-ahead bias, and benchmarked against baseline models on identical sample sets.

```mermaid
flowchart TD
    subgraph Data Layer
        A[yfinance Provider] -->|Validated Ingestion| B[(PostgreSQL 16)]
        B --> C[stock_price partitioned]
        B --> D[corporate_action]
    end

    subgraph Prediction & Accountability Ledger
        C --> E[ML Pipeline: Baselines & Prophet]
        E --> F[(prediction immutable ledger)]
        F --> G[Resolution Engine]
        C --> G
        G --> H[(prediction_outcome)]
        H --> I[mv_model_scorecard]
    end

    subgraph Presentation & API Layer
        I --> J[FastAPI Backend / REST API]
        I --> K[Streamlit Interactive Dashboard]
        J --> K
    end
```

## Quickstart

### Prerequisites
- Python 3.11
- PostgreSQL 16 (or local PostgreSQL service) / Docker Compose

### 1. Installation & Environment Setup

```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Database Initialization & Migrations

```bash
# Initialize roles and target database
python db/init_roles.py

# Run migrations
python db/migrate.py
```

### 3. Start Backend & Verification

```bash
uvicorn app.main:app --reload
```

Health check:
```bash
curl http://localhost:8000/health
# Response: {"db": "ok"}
```

### 4. Run Tests

```bash
pytest -v
```
