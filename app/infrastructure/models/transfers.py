import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.domain.enums import TransferStatus
from .base import Base


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"))
    to_merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    idempotency_key: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)
    status: Mapped[TransferStatus] = mapped_column(SAEnum(TransferStatus), default=TransferStatus.WAIT_PAYMENT)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())