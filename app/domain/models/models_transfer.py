from app.domain.enums.transfer import TransferStatus

from uuid import UUID
from decimal import Decimal
from dataclasses import dataclass


@dataclass(frozen=True)
class TransferRequest:
    idempotency_key: str
    from_merchant_name: str
    to_merchant_name: str
    currency: str
    amount: Decimal

@dataclass(frozen=True)
class TransferRequestRepository:
    from_merchant_id: UUID
    to_merchant_id: UUID
    currency: str
    amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal
    idempotency_key: str
    status: TransferStatus

@dataclass(frozen=True)
class TransferFilter:
    from_merchant_id: UUID | None = None
    to_merchant_id: UUID | None = None
    currency: str | None = None

@dataclass(frozen=True)
class TransferListQuery:
    from_merchant: str | None = None
    to_merchant: str | None = None
    currency: str | None = None
    