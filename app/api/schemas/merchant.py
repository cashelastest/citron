from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

from app.api.schemas.money import CurrencyCode, Money


class MerchantCreateRequest(BaseModel):
    merchant_name: str = Field(min_length=1, max_length=100)
    currency: CurrencyCode
    initial_balance: Decimal = Field(ge=0)


class BalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    amount: Money


class MerchantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_name: str
    balances: list[BalanceResponse] = []