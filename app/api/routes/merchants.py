from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas import BalanceResponse, MerchantCreateRequest, MerchantResponse
from app.domain.services.merchant_service import MerchantService
from app.infrastructure.deps import get_merchant_service

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.post("", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant(
    payload: MerchantCreateRequest,
    service: Annotated[MerchantService, Depends(get_merchant_service)],
):
    merchant, balances = await service.create_merchant(
        payload.merchant_name, payload.currency, payload.initial_balance
    )
    return MerchantResponse(
        id=merchant.id,
        merchant_name=merchant.merchant_name,
        balances=[BalanceResponse.model_validate(b) for b in balances],
    )


@router.get("/{merchant_name}", response_model=MerchantResponse)
async def get_merchant(
    merchant_name: str,
    service: Annotated[MerchantService, Depends(get_merchant_service)],
):
    merchant, balances = await service.get_merchant(merchant_name)
    return MerchantResponse(
        id=merchant.id,
        merchant_name=merchant.merchant_name,
        balances=[BalanceResponse.model_validate(b) for b in balances],
    )


@router.get("/{merchant_name}/balance", response_model=list[BalanceResponse])
async def get_merchant_balance(
    merchant_name: str,
    service: Annotated[MerchantService, Depends(get_merchant_service)],
):
    return await service.get_balances(merchant_name)
