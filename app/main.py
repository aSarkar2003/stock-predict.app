from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from app.db import check_db_health, close_pools


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pools()


app = FastAPI(
    title="STOCK&PREDICT",
    description="Stock direction prediction and model accountability platform",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health endpoint checking database connectivity.
    Returns {"db": "ok"} when PostgreSQL is available.
    """
    is_healthy = check_db_health()
    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"db": "unavailable", "message": "Database health check failed"},
        )
    return {"db": "ok"}

