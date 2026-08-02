from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.routes import merchants_router, transfers_router
from app.config import settings
from app.logging_config import setup_logging


def create_app() -> FastAPI:
    setup_logging(debug=settings.debug)

    app = FastAPI(title="Mini Ledger", version="0.1.0")

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(merchants_router)
    app.include_router(transfers_router)

    return app


app = create_app()
