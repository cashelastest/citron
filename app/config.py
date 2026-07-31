from decimal import Decimal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    FEE_PERCENT = Decimal("0.01")
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()