from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.infrastructure.models import Merchant, Transfer
from app.domain.models import TransferDTO, TransferRequestRepository, TransferFilter
from app.domain.exceptions import DuplicateIdempotencyKeyError


class TransferRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _to_dto(transfer: Transfer, from_merchant_name: str, to_merchant_name: str) -> TransferDTO:
        return TransferDTO(
            id=transfer.id,
            from_merchant_id=transfer.from_merchant_id,
            to_merchant_id=transfer.to_merchant_id,
            from_merchant_name=from_merchant_name,
            to_merchant_name=to_merchant_name,
            currency=transfer.currency,
            amount=transfer.amount,
            fee_amount=transfer.fee_amount,
            total_amount=transfer.total_amount,
            idempotency_key=transfer.idempotency_key,
            status=transfer.status,
            created_at=transfer.created_at,
        )

    @staticmethod
    def _select_with_names() -> Select:
        """Transfers joined to both sides, so the API can show names, not UUIDs."""
        source = aliased(Merchant)
        target = aliased(Merchant)
        return (
            select(Transfer, source.merchant_name, target.merchant_name)
            .join(source, Transfer.from_merchant_id == source.id)
            .join(target, Transfer.to_merchant_id == target.id)
        )

    async def _get_one(self, *conditions) -> TransferDTO | None:
        result = await self.session.execute(self._select_with_names().where(*conditions))
        row = result.first()
        return self._to_dto(*row) if row else None

    async def create(self, transfer_data: TransferRequestRepository) -> TransferDTO:
        transfer = Transfer(**transfer_data.__dict__)
        self.session.add(transfer)
        try:
            # Flushing here, rather than at commit, is what lets the collision
            # surface while the caller can still roll back and re-read.
            await self.session.flush()
        except IntegrityError as exc:
            # idempotency_key carries the only unique constraint on transfers.
            raise DuplicateIdempotencyKeyError(transfer_data.idempotency_key) from exc

        return await self._get_one(Transfer.id == transfer.id)

    async def get_by_idempotency_key(self, key: str) -> TransferDTO | None:
        return await self._get_one(Transfer.idempotency_key == key)

    async def list(self, transfer_filter: TransferFilter) -> list[TransferDTO]:
        stmt = self._select_with_names()
        if transfer_filter.from_merchant_id is not None:
            stmt = stmt.where(Transfer.from_merchant_id == transfer_filter.from_merchant_id)
        if transfer_filter.to_merchant_id is not None:
            stmt = stmt.where(Transfer.to_merchant_id == transfer_filter.to_merchant_id)
        if transfer_filter.currency is not None:
            stmt = stmt.where(Transfer.currency == transfer_filter.currency)

        result = await self.session.execute(stmt.order_by(Transfer.created_at.desc()))
        return [self._to_dto(*row) for row in result.all()]
