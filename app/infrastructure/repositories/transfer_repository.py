from sqlalchemy import select

from app.infrastructure.models import Transfer
from app.domain.models import TransferDTO, TransferRequestRepository


class TransferRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _to_dto(transfer: Transfer) -> TransferDTO:
        return TransferDTO(
            id=transfer.id,
            from_merchant_id=transfer.from_merchant_id,
            to_merchant_id=transfer.to_merchant_id,
            currency=transfer.currency,
            amount=transfer.amount,
            fee_amount=transfer.fee_amount,
            total_amount=transfer.total_amount,
            idempotency_key=transfer.idempotency_key,
            status=transfer.status,
            created_at=transfer.created_at,
        )

    async def create(self, transfer_data: TransferRequestRepository) -> TransferDTO:
        transfer = Transfer(**transfer_data.__dict__)
        self.session.add(transfer)
        await self.session.flush()
        return self._to_dto(transfer)

    async def get_by_idempotency_key(self, key: str) -> TransferDTO | None:
        stmt = select(Transfer).where(Transfer.idempotency_key == key)
        result = await self.session.execute(stmt)
        transfer = result.scalar_one_or_none()
        return self._to_dto(transfer) if transfer else None