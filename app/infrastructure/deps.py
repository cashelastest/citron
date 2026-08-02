from typing import AsyncIterator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.db import get_session
from app.infrastructure.unit_of_work import UnitOfWork
from app.domain.services.fee_calculator import FeeCalculator
from app.domain.services.merchant_service import MerchantService
from app.domain.services.transfer_service import TransferService


async def get_uow(session: AsyncSession = Depends(get_session)) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(session) as uow:
        yield uow


def get_fee_calculator() -> FeeCalculator:
    """Single place where the fee policy is read from configuration."""
    return FeeCalculator(settings.FEE_PERCENT)


async def get_merchant_service(uow: UnitOfWork = Depends(get_uow)) -> MerchantService:
    return MerchantService(uow)


async def get_transfer_service(
    uow: UnitOfWork = Depends(get_uow),
    fee_calculator: FeeCalculator = Depends(get_fee_calculator),
) -> TransferService:
    return TransferService(uow, fee_calculator)
