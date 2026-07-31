from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.merchant_repository import MerchantRepository
from app.infrastructure.repositories.balance_repository import BalanceRepository
from app.infrastructure.repositories.transfer_repository import TransferRepository


class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.merchants = MerchantRepository(session)
        self.balances = BalanceRepository(session)
        self.transfers = TransferRepository(session)

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()