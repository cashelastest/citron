from app.infrastructure.unit_of_work import UnitOfWork
from app.domain.models import TransferRequest, TransferDTO, TransferRequestRepository
from app.domain.enums import TransferStatus
from app.domain.exceptions import MerchantNotFoundError
from app.config import settings

from decimal import Decimal
from loguru import logger


class TransferService:

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    @staticmethod
    def _calculate_fee(amount: Decimal) -> Decimal:
        return (amount * settings.FEE_PERCENT).quantize(Decimal("0.00000001"))

    async def execute_transfer(self, request_data: TransferRequest) -> TransferDTO: 

        existing = await self.uow.transfers.get_by_idempotency_key(request_data.idempotency_key)
        if existing is not None:
            logger.info(f"Idempotent hit for key={request_data.idempotency_key}")

        from_merchant = await self.uow.merchants.get_by_name(request_data.from_merchant_name)
        if from_merchant is None:
            raise MerchantNotFoundError(request_data.from_merchant_name)

        to_merchant = await self.uow.merchants.get_by_name(request_data.to_merchant_name)
        if to_merchant is None:
            raise MerchantNotFoundError(request_data.to_merchant_name)
        fee_amount = self._calculate_fee(request_data.amount)
        total_amount = request_data.amount + fee_amount
        await self.uow.balances.debit(from_merchant.id, request_data.currency, total_amount)
        await self.uow.balances.credit(to_merchant.id, request_data.currency, total_amount)

        transfer_data = TransferRequestRepository(
            from_merchant_id=from_merchant.id,
            to_merchant_id=to_merchant.id,
            currency=request_data.currency,
            amount=request_data.amount,
            fee_amount=fee_amount,
            total_amount=total_amount,
            idempotency_key=request_data.idempotency_key,
            status=TransferStatus.DONE,
        )

        transfer = await self.uow.transfers.create(transfer_data = transfer_data)
        await self.uow.commit()
        return transfer