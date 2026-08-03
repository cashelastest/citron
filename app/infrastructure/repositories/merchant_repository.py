from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import Merchant
from app.domain.models import MerchantDTO
from app.domain.exceptions import MerchantAlreadyExistsError


class MerchantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dto(merchant: Merchant) -> MerchantDTO:
        return MerchantDTO(
            id=merchant.id,
            merchant_name=merchant.merchant_name,
        )

    async def get_by_name(self, merchant_name: str) -> MerchantDTO | None:
        stmt = select(Merchant).where(Merchant.merchant_name == merchant_name)
        result = await self.session.execute(stmt)
        merchant = result.scalar_one_or_none()
        return self._to_dto(merchant) if merchant else None

    async def create(self, merchant_name: str) -> MerchantDTO:
        merchant = Merchant(merchant_name=merchant_name)
        self.session.add(merchant)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            # merchant_name carries the only unique constraint on merchants.
            # The service's exists() check is a fast path; this is what actually
            # holds when two requests create the same name at the same time.
            raise MerchantAlreadyExistsError(merchant_name) from exc

        return self._to_dto(merchant)

    async def exists(self, merchant_name: str) -> bool:
        return await self.get_by_name(merchant_name) is not None
