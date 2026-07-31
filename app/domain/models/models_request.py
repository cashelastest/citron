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
    idempotency_key: UUID
    status: TransferStatus