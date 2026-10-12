"""
Database migration runner.
Discovers and applies versioned SQL migrations in ordered sequence.
"""
import os
import sys
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "stock_predict")
PGUSER_OWNER = os.getenv("PGUSER_OWNER", "app_owner")
PGPASSWORD_OWNER = os.getenv("PGPASSWORD_OWNER", "app_owner_pass")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations():
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Connecting to {PGDATABASE} as owner {PGUSER_OWNER} on {PGHOST}:{PGPORT}...")

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
            # Create schema_migrations tracker table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

            cur.execute("SELECT version FROM schema_migrations;")
            applied_versions = {row[0] for row in cur.fetchall()}

            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            applied_count = 0

            for filepath in migration_files:
                version = filepath.name
                if version not in applied_versions:
                    print(f"Applying migration: {version}...")
                    sql_content = filepath.read_text(encoding="utf-8")
                    if sql_content.strip():
                        cur.execute(sql_content)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s);",
                        (version,)
                    )
                    conn.commit()
                    applied_count += 1
                    print(f"Applied: {version}")
                else:
                    print(f"Already applied: {version}")

            if applied_count == 0:
                print("No pending migrations. Schema is up to date.")
            else:
                print(f"Successfully applied {applied_count} migrations.")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}", file=sys.stderr)
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()

