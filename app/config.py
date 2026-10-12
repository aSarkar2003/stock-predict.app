from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGDATABASE: str = "stock_predict"

    PGUSER_ADMIN: str = "postgres"
    PGPASSWORD_ADMIN: str = "admin"

    PGUSER_OWNER: str = "app_owner"
    PGPASSWORD_OWNER: str = "app_owner_pass"

    PGUSER_RW: str = "app_rw"
    PGPASSWORD_RW: str = "app_rw_pass"

    PGUSER_RO: str = "app_ro"
    PGPASSWORD_RO: str = "app_ro_pass"

    JWT_SECRET: str = "super-secret-jwt-key-for-stock-predict-application-dev"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

