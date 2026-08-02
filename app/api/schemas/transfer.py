from uuid import UUID
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.api.schemas.money import CurrencyCode, Money
from app.domain.enums import TransferStatus


class TransferCreateRequest(BaseModel):
    from_merchant: str = Field(min_length=1)
    to_merchant: str = Field(min_length=1)
    currency: CurrencyCode
    amount: Decimal = Field(gt=0)


class TransferListParams(BaseModel):
    """Query string of GET /transfers. `from` is a keyword, hence the aliases."""

    from_merchant: str | None = Field(default=None, alias="from")
    to_merchant: str | None = Field(default=None, alias="to")
    currency: CurrencyCode | None = None


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_merchant: str = Field(validation_alias="from_merchant_name")
    to_merchant: str = Field(validation_alias="to_merchant_name")
    currency: str
    amount: Money
    fee_amount: Money
    total_amount: Money
    status: TransferStatus
    idempotency_key: str
    created_at: datetime
