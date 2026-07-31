from typing import AsyncIterator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import get_session
from app.infrastructure.unit_of_work import UnitOfWork


async def get_uow(session: AsyncSession = Depends(get_session)) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(session) as uow:
        yield uow