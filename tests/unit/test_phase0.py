from fastapi.testclient import TestClient
import psycopg
import pytest
from app.main import app
from app.config import settings

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"db": "ok"}


def test_app_rw_role_current_user():
    """Verify connecting as app_rw returns app_rw as current_user."""
    conn = psycopg.connect(
        host=settings.PGHOST,
        port=settings.PGPORT,
        dbname=settings.PGDATABASE,
        user=settings.PGUSER_RW,
        password=settings.PGPASSWORD_RW,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user;")
            user = cur.fetchone()[0]
            assert user == settings.PGUSER_RW
    finally:
        conn.close()


def test_db_failure_safeguard():
    """Verify connection fails cleanly when invalid port/credentials are used."""
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(
            host=settings.PGHOST,
            port=5439,  # Non-existent port
            dbname=settings.PGDATABASE,
            user=settings.PGUSER_RW,
            password=settings.PGPASSWORD_RW,
            connect_timeout=2,
        )

