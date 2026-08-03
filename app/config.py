from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # The compose database. Dropped and recreated on every test run.
    test_database_url: str = (
        "postgresql+asyncpg://ledger_user:ledger_pass@localhost:5432/citron_test"
    )
    FEE_PERCENT: Decimal = Decimal("0.01")
    debug: bool = False


settings = Settings()
