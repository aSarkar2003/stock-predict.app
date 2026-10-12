-- Migration 008: Role Permissions & Default Privileges

-- Grants for app_rw role (Read/Write application API user)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;

-- Grants for app_ro role (Read-Only reporting user)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_ro;

-- Default Privileges for future objects created in schema public by app_owner
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_rw;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_ro;
