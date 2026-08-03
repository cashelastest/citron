import logging
from uuid import UUID

from app.infrastructure.unit_of_work import UnitOfWork
from app.domain.models import (
    TransferRequest,
    TransferDTO,
    TransferRequestRepository,
    TransferFilter,
    TransferListQuery,
)
from app.domain.enums import TransferStatus
from app.domain.exceptions import (
    DuplicateIdempotencyKeyError,
    MerchantNotFoundError,
    SameMerchantTransferError,
)
from app.domain.services.fee_calculator import FeeCalculator

logger = logging.getLogger(__name__)


class TransferService:

    def __init__(self, uow: UnitOfWork, fee_calculator: FeeCalculator):
        self.uow = uow
        self.fee_calculator = fee_calculator

    async def _resolve_merchant_id(self, merchant_name: str) -> UUID:
        merchant = await self.uow.merchants.get_by_name(merchant_name)
        if merchant is None:
            raise MerchantNotFoundError(merchant_name)
        return merchant.id

    async def execute_transfer(self, request_data: TransferRequest) -> TransferDTO:
        if request_data.from_merchant_name == request_data.to_merchant_name:
            raise SameMerchantTransferError(request_data.from_merchant_name)

        existing = await self.uow.transfers.get_by_idempotency_key(request_data.idempotency_key)
        if existing is not None:
            logger.info(
                "transfer_idempotent_hit",
                extra={
                    "idempotency_key": request_data.idempotency_key,
                    "transfer_id": str(existing.id),
                    "source": "replay",
                },
            )
            return existing

        from_merchant_id = await self._resolve_merchant_id(request_data.from_merchant_name)
        to_merchant_id = await self._resolve_merchant_id(request_data.to_merchant_name)

        fee_amount = self.fee_calculator.calculate(request_data.amount)
        total_amount = request_data.amount + fee_amount

        await self.uow.balances.move(
            from_merchant_id=from_merchant_id,
            to_merchant_id=to_merchant_id,
            currency=request_data.currency,
            debit_amount=total_amount,
            credit_amount=request_data.amount,
        )

        transfer_data = TransferRequestRepository(
            from_merchant_id=from_merchant_id,
            to_merchant_id=to_merchant_id,
            currency=request_data.currency,
            amount=request_data.amount,
            fee_amount=fee_amount,
            total_amount=total_amount,
            idempotency_key=request_data.idempotency_key,
            status=TransferStatus.DONE,
        )
        try:
            transfer = await self.uow.transfers.create(transfer_data=transfer_data)
            await self.uow.commit()
            logger.info(
                "transfer_executed",
                extra={
                    "transfer_id": str(transfer.id),
                    "idempotency_key": request_data.idempotency_key,
                    "from_merchant": request_data.from_merchant_name,
                    "to_merchant": request_data.to_merchant_name,
                    "currency": request_data.currency,
                    "amount": str(request_data.amount),
                    "fee_amount": str(fee_amount),
                    "total_amount": str(total_amount),
                },
            )
            return transfer
        except DuplicateIdempotencyKeyError:
            # Another request with the same key won the race and committed first.
            # Rollback is mandatory before any further select: the transaction is
            # aborted, and it also discards the balance changes made above.
            await self.uow.rollback()
            existing = await self.uow.transfers.get_by_idempotency_key(request_data.idempotency_key)
            logger.info(
                "transfer_idempotent_hit",
                extra={
                    "idempotency_key": request_data.idempotency_key,
                    "transfer_id": str(existing.id) if existing else None,
                    "source": "race",
                },
            )
            return existing

    async def list_transfers(self, query: TransferListQuery) -> list[TransferDTO]:
        transfer_filter = TransferFilter(
            from_merchant_id=(
                await self._resolve_merchant_id(query.from_merchant)
                if query.from_merchant is not None
                else None
            ),
            to_merchant_id=(
                await self._resolve_merchant_id(query.to_merchant)
                if query.to_merchant is not None
                else None
            ),
            currency=query.currency,
        )
        return await self.uow.transfers.list(transfer_filter)
