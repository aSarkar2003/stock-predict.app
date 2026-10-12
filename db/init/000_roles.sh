#!/bin/bash
set -e

echo "Setting up PostgreSQL roles and database for STOCK&PREDICT..."

# Create database if not exists
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 1. App Owner Role (Schema owner and migration executor)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${PGUSER_OWNER:-app_owner}') THEN
            CREATE ROLE ${PGUSER_OWNER:-app_owner} WITH LOGIN PASSWORD '${PGPASSWORD_OWNER:-app_owner_pass}';
        END IF;
    END
    \$\$;

    -- 2. App Read/Write Role (Application API user)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${PGUSER_RW:-app_rw}') THEN
            CREATE ROLE ${PGUSER_RW:-app_rw} WITH LOGIN PASSWORD '${PGPASSWORD_RW:-app_rw_pass}';
        END IF;
    END
    \$\$;

    -- 3. App Read-Only Role (Reporting / Analytics user)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${PGUSER_RO:-app_ro}') THEN
            CREATE ROLE ${PGUSER_RO:-app_ro} WITH LOGIN PASSWORD '${PGPASSWORD_RO:-app_ro_pass}';
        END IF;
    END
    \$\$;

    -- Grant database connection permissions
    GRANT CONNECT ON DATABASE ${PGDATABASE:-stock_predict} TO ${PGUSER_OWNER:-app_owner};
    GRANT CONNECT ON DATABASE ${PGDATABASE:-stock_predict} TO ${PGUSER_RW:-app_rw};
    GRANT CONNECT ON DATABASE ${PGDATABASE:-stock_predict} TO ${PGUSER_RO:-app_ro};

    -- Grant schema creation and usage to app_owner
    GRANT USAGE, CREATE ON SCHEMA public TO ${PGUSER_OWNER:-app_owner};
    ALTER SCHEMA public OWNER TO ${PGUSER_OWNER:-app_owner};

    -- Grant schema usage to app_rw and app_ro
    GRANT USAGE ON SCHEMA public TO ${PGUSER_RW:-app_rw};
    GRANT USAGE ON SCHEMA public TO ${PGUSER_RO:-app_ro};
EOSQL

echo "Roles and database setup complete."

