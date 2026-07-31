import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
if TYPE_CHECKING:
    from .merchants import Merchant


class Balance(Base):
    __tablename__ = "balances"
    __table_args__ = (
        UniqueConstraint("merchant_id", "currency", name="uq_merchant_currency"),
        CheckConstraint("amount >= 0", name="ck_balance_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"))
    currency: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))

    merchant: Mapped["Merchant"] = relationship(back_populates="balances")