from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.schemas import TransferCreateRequest, TransferListParams, TransferResponse
from app.domain.models import TransferRequest, TransferListQuery
from app.domain.exceptions import InvalidIdempotencyKeyError
from app.domain.services.transfer_service import TransferService
from app.infrastructure.deps import get_transfer_service

router = APIRouter(prefix="/transfers", tags=["transfers"])

MAX_IDEMPOTENCY_KEY_LENGTH = 255


def idempotency_key(
    key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """Validated here rather than by a required Header(...), so a missing key
    comes back in the same error shape as every other domain error."""
    if key is None:
        raise InvalidIdempotencyKeyError("header 'Idempotency-Key' is required")

    key = key.strip()
    if not key:
        raise InvalidIdempotencyKeyError("header 'Idempotency-Key' must not be blank")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise InvalidIdempotencyKeyError(
            f"header 'Idempotency-Key' must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters"
        )
    return key


@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def execute_transfer(
    payload: TransferCreateRequest,
    key: Annotated[str, Depends(idempotency_key)],
    service: Annotated[TransferService, Depends(get_transfer_service)],
):
    return await service.execute_transfer(
        TransferRequest(
            idempotency_key=key,
            from_merchant_name=payload.from_merchant,
            to_merchant_name=payload.to_merchant,
            currency=payload.currency,
            amount=payload.amount,
        )
    )


@router.get("", response_model=list[TransferResponse])
async def list_transfers(
    params: Annotated[TransferListParams, Query()],
    service: Annotated[TransferService, Depends(get_transfer_service)],
):
    return await service.list_transfers(TransferListQuery(**params.model_dump()))
