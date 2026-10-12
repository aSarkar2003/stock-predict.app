"""
Database role and initial schema permission script for local or CI setups.
Can be executed directly on any platform with python db/init_roles.py
"""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "stock_predict")
PGUSER_ADMIN = os.getenv("PGUSER_ADMIN", "postgres")
PGPASSWORD_ADMIN = os.getenv("PGPASSWORD_ADMIN", "admin")

PGUSER_OWNER = os.getenv("PGUSER_OWNER", "app_owner")
PGPASSWORD_OWNER = os.getenv("PGPASSWORD_OWNER", "app_owner_pass")
PGUSER_RW = os.getenv("PGUSER_RW", "app_rw")
PGPASSWORD_RW = os.getenv("PGPASSWORD_RW", "app_rw_pass")
PGUSER_RO = os.getenv("PGUSER_RO", "app_ro")
PGPASSWORD_RO = os.getenv("PGPASSWORD_RO", "app_ro_pass")


def init_roles_and_db():
    print(f"Connecting as admin '{PGUSER_ADMIN}' to PostgreSQL at {PGHOST}:{PGPORT}...")
    # Connect to default 'postgres' database to ensure PGDATABASE exists
    conn_admin = psycopg.connect(
        host=PGHOST,
        port=PGPORT,
        dbname="postgres",
        user=PGUSER_ADMIN,
        password=PGPASSWORD_ADMIN,
        autocommit=True,
    )
    try:
        with conn_admin.cursor() as cur:
            # Check if database exists
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (PGDATABASE,))
            if not cur.fetchone():
                print(f"Creating database '{PGDATABASE}'...")
                cur.execute(f'CREATE DATABASE "{PGDATABASE}";')
            else:
                print(f"Database '{PGDATABASE}' already exists.")
    finally:
        conn_admin.close()

    # Now connect to target database PGDATABASE as admin
    conn = psycopg.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER_ADMIN,
        password=PGPASSWORD_ADMIN,
        autocommit=True,
    )

    try:
        with conn.cursor() as cur:
            print("Creating roles if not present...")
            # 1. app_owner
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{PGUSER_OWNER}') THEN
                        CREATE ROLE {PGUSER_OWNER} WITH LOGIN PASSWORD '{PGPASSWORD_OWNER}';
                    ELSE
                        ALTER ROLE {PGUSER_OWNER} WITH PASSWORD '{PGPASSWORD_OWNER}';
                    END IF;
                END
                $$;
            """)

            # 2. app_rw
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{PGUSER_RW}') THEN
                        CREATE ROLE {PGUSER_RW} WITH LOGIN PASSWORD '{PGPASSWORD_RW}';
                    ELSE
                        ALTER ROLE {PGUSER_RW} WITH PASSWORD '{PGPASSWORD_RW}';
                    END IF;
                END
                $$;
            """)

            # 3. app_ro
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{PGUSER_RO}') THEN
                        CREATE ROLE {PGUSER_RO} WITH LOGIN PASSWORD '{PGPASSWORD_RO}';
                    ELSE
                        ALTER ROLE {PGUSER_RO} WITH PASSWORD '{PGPASSWORD_RO}';
                    END IF;
                END
                $$;
            """)

            # Grant database connection permissions
            cur.execute(f"GRANT CONNECT ON DATABASE \"{PGDATABASE}\" TO {PGUSER_OWNER};")
            cur.execute(f"GRANT CONNECT ON DATABASE \"{PGDATABASE}\" TO {PGUSER_RW};")
            cur.execute(f"GRANT CONNECT ON DATABASE \"{PGDATABASE}\" TO {PGUSER_RO};")

            # Schema permissions
            cur.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {PGUSER_OWNER};")
            cur.execute(f"ALTER SCHEMA public OWNER TO {PGUSER_OWNER};")

            cur.execute(f"GRANT USAGE ON SCHEMA public TO {PGUSER_RW};")
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {PGUSER_RO};")

            print("Database roles and initial permissions successfully configured!")
    finally:
        conn.close()


if __name__ == "__main__":
    init_roles_and_db()

