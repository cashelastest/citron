import asyncio
import os
from decimal import Decimal
from pathlib import Path
from typing import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.infrastructure.db import get_session
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", settings.database_url.rsplit("/", 1)[0] + "/citron_test"
)


def _asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _run_migrations() -> None:
    """Build the schema the same way production does.

    Base.metadata.create_all would be faster, but it builds the schema from the
    models — so a migration that drifted from them would still pass every test.
    """
    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_config, "head")


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator:
    """A real Postgres database, not SQLite.

    The whole point of these tests is SELECT ... FOR UPDATE, ON CONFLICT and
    NUMERIC(20, 8); on SQLite they would pass while proving nothing.
    """
    dsn, name = _asyncpg_dsn(TEST_DATABASE_URL).rsplit("/", 1)
    admin = await asyncpg.connect(f"{dsn}/postgres")
    await admin.execute(
        f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'
    )
    await admin.execute(f'CREATE DATABASE "{name}"')
    await admin.close()

    # alembic's env.py calls asyncio.run(), which cannot nest inside the loop
    # pytest-asyncio is already running — hence the worker thread.
    await asyncio.to_thread(_run_migrations)

    test_engine = create_async_engine(TEST_DATABASE_URL, pool_size=25, max_overflow=10)
    yield test_engine

    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(engine):
    """Truncate instead of wrapping each test in a rollback: the concurrency
    tests need several connections to really commit and see each other."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE transfers, balances, merchants CASCADE"))
    yield


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def merchant(client):
    """Creates a merchant and returns its name."""

    async def _create(name: str, currency: str = "BTC", initial: str = "0") -> str:
        response = await client.post(
            "/merchants",
            json={
                "merchant_name": name,
                "currency": currency,
                "initial_balance": initial,
            },
        )
        assert response.status_code == 201, response.text
        return name

    return _create


@pytest.fixture
def transfer_body():
    def _body(sender: str, receiver: str, amount: str, currency: str = "BTC") -> dict:
        return {
            "from_merchant": sender,
            "to_merchant": receiver,
            "currency": currency,
            "amount": amount,
        }

    return _body


async def balance_of(client: AsyncClient, name: str, currency: str = "BTC") -> Decimal:
    response = await client.get(f"/merchants/{name}/balance")
    assert response.status_code == 200, response.text
    for entry in response.json():
        if entry["currency"] == currency:
            return Decimal(entry["amount"])
    raise AssertionError(f"{name} holds no {currency}: {response.json()}")
