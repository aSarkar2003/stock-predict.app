"""
Seed baseline reference data and models for STOCK&PREDICT.
Populates:
- 3 system users (admin, analyst, viewer) with Argon2 password hashes
- Representative Indian industries
- 10 representative Indian stock tickers (NSE)
- Trading calendar for 2015-2027 distinguishing trading sessions from weekends and NSE holidays
- Baseline models ('naive_last' and 'drift') with initial versions
"""
import os
import datetime
import psycopg
from argon2 import PasswordHasher
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "stock_predict_clean")
PGUSER_OWNER = os.getenv("PGUSER_OWNER", "app_owner")
PGPASSWORD_OWNER = os.getenv("PGPASSWORD_OWNER", "app_owner_pass")

ph = PasswordHasher()

# Documented standard NSE holiday list (key observed exchange holidays)
# Official Source: National Stock Exchange of India (NSE) Circulars on Trading Holidays
NSE_ANNUAL_FIXED_HOLIDAYS = {
    (1, 26): "Republic Day",
    (5, 1): "Maharashtra Day / Labour Day",
    (8, 15): "Independence Day",
    (10, 2): "Mahatma Gandhi Jayanti",
    (12, 25): "Christmas",
}


def is_nse_holiday(dt: datetime.date) -> tuple[bool, str | None]:
    if dt.weekday() in (5, 6):
        return True, "Weekend"
    
    # Check fixed national holidays
    if (dt.month, dt.day) in NSE_ANNUAL_FIXED_HOLIDAYS:
        return True, NSE_ANNUAL_FIXED_HOLIDAYS[(dt.month, dt.day)]
    
    return False, None


def seed_database():
    print(f"Seeding database '{PGDATABASE}' as owner '{PGUSER_OWNER}'...")
    conn = psycopg.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER_OWNER,
        password=PGPASSWORD_OWNER,
        autocommit=False,
    )

    try:
        with conn.cursor() as cur:
            # 1. System Users
            print("1. Seeding system users...")
            users = [
                ("admin_user", "admin@stockpredict.org", ph.hash("AdminPass123!"), "admin"),
                ("analyst_user", "analyst@stockpredict.org", ph.hash("AnalystPass123!"), "analyst"),
                ("viewer_user", "viewer@stockpredict.org", ph.hash("ViewerPass123!"), "viewer"),
            ]
            for username, email, pw_hash, role in users:
                cur.execute("""
                    INSERT INTO app_user (username, email, password_hash, role)
                    VALUES (%s, %s, %s, %s::app_role)
                    ON CONFLICT (username) DO NOTHING;
                """, (username, email, pw_hash, role))

            # 2. Industries
            print("2. Seeding industries...")
            industries = [
                "Conglomerate",
                "Information Technology",
                "Banking & Financial Services",
                "Energy & Power",
                "Automotive",
                "Consumer Goods",
                "Construction & Infrastructure",
                "Telecommunications",
                "Pharmaceuticals",
                "Metals & Mining",
            ]
            industry_id_map = {}
            for ind_name in industries:
                cur.execute("""
                    INSERT INTO industry (name) VALUES (%s)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING industry_id, name;
                """, (ind_name,))
                row = cur.fetchone()
                if row:
                    industry_id_map[row[1]] = row[0]

            # 3. 10 Representative Indian Stock Tickers
            print("3. Seeding representative Indian stock tickers...")
            tickers = [
                ("RELIANCE", "Reliance Industries Ltd", "Conglomerate"),
                ("TCS", "Tata Consultancy Services Ltd", "Information Technology"),
                ("INFY", "Infosys Ltd", "Information Technology"),
                ("HDFCBANK", "HDFC Bank Ltd", "Banking & Financial Services"),
                ("ICICIBANK", "ICICI Bank Ltd", "Banking & Financial Services"),
                ("KOTAKBANK", "Kotak Mahindra Bank Ltd", "Banking & Financial Services"),
                ("LT", "Larsen & Toubro Ltd", "Construction & Infrastructure"),
                ("ITC", "ITC Ltd", "Consumer Goods"),
                ("SBIN", "State Bank of India", "Banking & Financial Services"),
                ("BHARTIARTL", "Bharti Airtel Ltd", "Telecommunications"),
            ]
            for symbol, full_name, ind_name in tickers:
                ind_id = industry_id_map.get(ind_name)
                cur.execute("""
                    INSERT INTO stock_ticker (symbol, exchange, name, industry_id)
                    VALUES (%s, 'NSE', %s, %s)
                    ON CONFLICT (symbol, exchange) DO UPDATE 
                    SET name = EXCLUDED.name, industry_id = EXCLUDED.industry_id;
                """, (symbol, full_name, ind_id))

            # 4. Trading Calendar 2015-2027
            print("4. Seeding trading calendar (2015-2027)...")
            start_date = datetime.date(2015, 1, 1)
            end_date = datetime.date(2027, 12, 31)
            curr = start_date
            calendar_rows = []
            
            while curr <= end_date:
                is_closed, reason = is_nse_holiday(curr)
                is_trading_day = not is_closed
                calendar_rows.append((curr, is_trading_day, reason))
                curr += datetime.timedelta(days=1)

            cur.executemany("""
                INSERT INTO trading_calendar (calendar_date, is_trading_day, notes)
                VALUES (%s, %s, %s)
                ON CONFLICT (calendar_date) DO NOTHING;
            """, calendar_rows)

            # 5. Baseline Models & Versions
            print("5. Seeding baseline models and versions...")
            baseline_models = [
                ("naive_last", "Tomorrow equals today baseline predicting zero return / unchanged price.", True),
                ("drift", "Linear drift baseline based on historical sample mean return.", True),
            ]
            for m_name, m_desc, is_base in baseline_models:
                cur.execute("""
                    INSERT INTO model (name, description, is_baseline)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE 
                    SET description = EXCLUDED.description, is_baseline = EXCLUDED.is_baseline
                    RETURNING model_id;
                """, (m_name, m_desc, is_base))
                model_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO model_version (model_id, version_tag, parameters)
                    VALUES (%s, 'v1.0.0', '{"description": "Baseline specification v1.0.0"}'::jsonb)
                    ON CONFLICT (model_id, version_tag) DO NOTHING;
                """, (model_id,))

            conn.commit()
            print("Seeding completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
