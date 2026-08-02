from dataclasses import dataclass
from decimal import Decimal
import uuid
from datetime import datetime

from app.domain.enums import TransferStatus

@dataclass(frozen=True)
class MerchantDTO:
    id: uuid.UUID
    merchant_name: str

@dataclass(frozen=True)
class BalanceDTO:
    currency: str
    amount: Decimal

@dataclass(frozen=True)
class TransferDTO:
    id: uuid.UUID
    from_merchant_id: uuid.UUID
    to_merchant_id: uuid.UUID
    from_merchant_name: str
    to_merchant_name: str
    currency: str
    amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal
    idempotency_key: str
    status: TransferStatus
    created_at: datetime