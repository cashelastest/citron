import uuid
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import Balance
from app.domain.models import BalanceDTO
from app.domain.exceptions import InsufficientFundsError, BalanceNotFoundError

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

    async def ensure_exists(self, merchant_id, currency: str) -> None:
        """Open a zero balance if the merchant has never held this currency.

        ON CONFLICT DO NOTHING instead of a select-then-insert: two concurrent
        transfers into the same new currency would otherwise race on
        uq_merchant_currency and abort the whole transaction.
        """
        stmt = (
            pg_insert(Balance)
            .values(
                id=uuid.uuid4(),
                merchant_id=merchant_id,
                currency=currency,
                amount=Decimal("0"),
            )
            .on_conflict_do_nothing(constraint="uq_merchant_currency")
        )
        await self.session.execute(stmt)

    async def move(
        self,
        from_merchant_id,
        to_merchant_id,
        currency: str,
        debit_amount: Decimal,
        credit_amount: Decimal,
    ) -> None:
        """Move funds between two balances within the caller's transaction.

        Both rows are locked in one globally agreed order (sorted by merchant id),
        so opposite transfers running at the same time queue up instead of
        deadlocking on SELECT ... FOR UPDATE.

        debit_amount and credit_amount differ by the fee: the sender pays
        amount + fee, the receiver is credited exactly amount.
        """
        await self.ensure_exists(to_merchant_id, currency)

        locked: dict[uuid.UUID, Balance] = {}
        for merchant_id in sorted((from_merchant_id, to_merchant_id)):
            locked[merchant_id] = await self.get_locked(merchant_id, currency)

        source = locked[from_merchant_id]
        target = locked[to_merchant_id]

        if source.amount < debit_amount:
            raise InsufficientFundsError(
                from_merchant_id, currency, debit_amount, source.amount
            )

        source.amount -= debit_amount
        target.amount += credit_amount