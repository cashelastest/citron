import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainError
from app.api.schemas import ErrorResponse


logger = logging.getLogger(__name__)


def _error_body(error_code: str, message: str, details: dict | None = None) -> dict:
    """jsonable_encoder, not model_dump: details carry raw values straight from
    the request (Decimal, UUID, datetime) that json.dumps cannot handle."""
    return jsonable_encoder(
        ErrorResponse(error_code=error_code, message=message, details=details)
    )


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        logger.info(
            "domain_error",
            extra={"error_code": exc.error_code, "path": request.url.path, "details": exc.details},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        logger.info("validation_error", extra={"path": request.url.path, "errors": exc.errors()})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body(
                "validation_error", "Invalid request data", {"errors": exc.errors()}
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "Internal server error"),
        )