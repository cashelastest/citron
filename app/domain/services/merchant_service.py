import logging
from decimal import Decimal

from app.infrastructure.unit_of_work import UnitOfWork
from app.domain.exceptions import MerchantAlreadyExistsError, MerchantNotFoundError
from app.domain.models import MerchantDTO, BalanceDTO

logger = logging.getLogger(__name__)


class MerchantService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def create_merchant(
        self, merchant_name: str, currency: str, initial_balance: Decimal
    ) -> tuple[MerchantDTO, list[BalanceDTO]]:
        if await self.uow.merchants.exists(merchant_name):
            raise MerchantAlreadyExistsError(merchant_name)

        merchant = await self.uow.merchants.create(merchant_name)
        balance = await self.uow.balances.create(merchant.id, currency, initial_balance)
        await self.uow.commit()

        logger.info(
            "merchant_created",
            extra={
                "merchant_id": str(merchant.id),
                "merchant_name": merchant_name,
                "currency": currency,
                "initial_balance": str(initial_balance),
            },
        )
        return merchant, [balance]

    async def get_merchant(self, merchant_name: str) -> tuple[MerchantDTO, list[BalanceDTO]]:
        merchant = await self.uow.merchants.get_by_name(merchant_name)
        if merchant is None:
            raise MerchantNotFoundError(merchant_name)

        balances = await self.uow.balances.list_for_merchant(merchant.id)
        return merchant, balances

    async def get_balances(self, merchant_name: str) -> list[BalanceDTO]:
        _, balances = await self.get_merchant(merchant_name)
        return balances