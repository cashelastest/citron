from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    FEE_PERCENT: Decimal = Decimal("0.01")
    debug: bool = False


settings = Settings()
