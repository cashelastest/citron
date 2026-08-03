import asyncio
from decimal import Decimal

from tests.conftest import balance_of


KEY = "abc-123-xyz"


async def test_replay_returns_the_same_transfer(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")
    body = transfer_body("alice_store", "bob_shop", "0.1")

    first = await client.post("/transfers", json=body, headers={"Idempotency-Key": KEY})
    second = await client.post("/transfers", json=body, headers={"Idempotency-Key": KEY})

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()


async def test_replay_charges_the_fee_only_once(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")
    body = transfer_body("alice_store", "bob_shop", "0.1")

    for _ in range(5):
        await client.post("/transfers", json=body, headers={"Idempotency-Key": KEY})

    assert await balance_of(client, "alice_store") == Decimal("0.899")
    assert await balance_of(client, "bob_shop") == Decimal("0.1")

    listing = await client.get("/transfers")
    assert len(listing.json()) == 1


async def test_different_keys_are_separate_transfers(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")
    body = transfer_body("alice_store", "bob_shop", "0.1")

    await client.post("/transfers", json=body, headers={"Idempotency-Key": "one"})
    await client.post("/transfers", json=body, headers={"Idempotency-Key": "two"})

    assert await balance_of(client, "alice_store") == Decimal("0.798")
    assert len((await client.get("/transfers")).json()) == 2


async def test_key_is_trimmed_before_comparison(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")
    body = transfer_body("alice_store", "bob_shop", "0.1")

    first = await client.post("/transfers", json=body, headers={"Idempotency-Key": KEY})
    second = await client.post("/transfers", json=body, headers={"Idempotency-Key": f"  {KEY}  "})

    assert first.json()["id"] == second.json()["id"]
    assert await balance_of(client, "alice_store") == Decimal("0.899")


async def test_concurrent_requests_with_one_key_settle_once(
    client, merchant, transfer_body
):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")
    body = transfer_body("alice_store", "bob_shop", "0.1")

    responses = await asyncio.gather(
        *[
            client.post("/transfers", json=body, headers={"Idempotency-Key": KEY})
            for _ in range(10)
        ]
    )

    assert {r.status_code for r in responses} == {201}
    assert len({r.json()["id"] for r in responses}) == 1

    assert await balance_of(client, "alice_store") == Decimal("0.899")
    assert await balance_of(client, "bob_shop") == Decimal("0.1")
    assert len((await client.get("/transfers")).json()) == 1
