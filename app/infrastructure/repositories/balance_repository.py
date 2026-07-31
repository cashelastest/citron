from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import Balance
from app.domain.models import BalanceDTO


class BalanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dto(balance: Balance) -> BalanceDTO:
        return BalanceDTO(
            currency=balance.currency,
            amount=balance.amount,
        )

    async def get(self, merchant_id, currency: str) -> BalanceDTO | None:
        stmt = select(Balance).where(
            Balance.merchant_id == merchant_id,
            Balance.currency == currency,
        )
        result = await self.session.execute(stmt)
        balance = result.scalar_one_or_none()
        return self._to_dto(balance) if balance else None

    async def create(self, merchant_id, currency: str, amount: Decimal) -> BalanceDTO:
        balance = Balance(merchant_id=merchant_id, currency=currency, amount=amount)
        self.session.add(balance)
        await self.session.flush()
        return self._to_dto(balance)

    async def list_for_merchant(self, merchant_id) -> list[BalanceDTO]:
        stmt = select(Balance).where(Balance.merchant_id == merchant_id)
        result = await self.session.execute(stmt)
        return [self._to_dto(b) for b in result.scalars().all()]

    async def get_locked(self, merchant_id, currency: str) -> Balance:
        stmt = (
            select(Balance)
            .where(Balance.merchant_id == merchant_id, Balance.currency == currency)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        balance = result.scalar_one_or_none()
        if balance is None:
            raise BalanceNotFoundError(merchant_id, currency)
        return balance

    async def debit(self, merchant_id, currency: str, total_amount: Decimal) -> None:
        balance = await self.get_locked(merchant_id, currency)
        if balance.amount < total_amount:
            raise InsufficientFundsError(merchant_id, currency, total_amount, balance.amount)
        balance.amount -= total_amount

    async def credit(self, merchant_id, currency: str, amount: Decimal) -> None:
        balance = await self.get_locked(merchant_id, currency)
        balance.amount += amount