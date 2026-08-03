import asyncio
from decimal import Decimal

from tests.conftest import balance_of


async def test_parallel_spending_never_drives_the_balance_negative(
    client, merchant, transfer_body
):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")
    body = transfer_body("alice_store", "bob_shop", "0.1")

    responses = await asyncio.gather(
        *[
            client.post("/transfers", json=body, headers={"Idempotency-Key": f"race-{i}"})
            for i in range(20)
        ]
    )

    settled = [r for r in responses if r.status_code == 201]
    rejected = [r for r in responses if r.status_code == 402]

    assert len(settled) + len(rejected) == 20, [r.status_code for r in responses]
    assert len(settled) == 9

    sender = await balance_of(client, "alice_store")
    receiver = await balance_of(client, "bob_shop")

    assert sender >= 0
    assert sender == Decimal("1") - len(settled) * Decimal("0.101")
    assert receiver == len(settled) * Decimal("0.1")
    assert len((await client.get("/transfers")).json()) == len(settled)


async def test_opposite_transfers_do_not_deadlock(client, merchant, transfer_body):
    """A -> B and B -> A at the same time.

    Locking the sender first and the receiver second would let two transactions
    hold one row each and wait for the other. Both rows are locked in merchant-id
    order instead, so these queue up rather than deadlocking.
    """
    await merchant("alice_store", initial="10")
    await merchant("bob_shop", initial="10")

    forward = transfer_body("alice_store", "bob_shop", "0.01")
    backward = transfer_body("bob_shop", "alice_store", "0.01")

    responses = await asyncio.gather(
        *[
            client.post(
                "/transfers",
                json=body,
                headers={"Idempotency-Key": f"{label}-{i}"},
            )
            for i in range(15)
            for label, body in (("fwd", forward), ("bwd", backward))
        ]
    )

    assert {r.status_code for r in responses} == {201}

    # Each side sent 15 x 0.01 and received 15 x 0.01, paying the fee both ways.
    expected = Decimal("10") - 15 * Decimal("0.0001")
    assert await balance_of(client, "alice_store") == expected
    assert await balance_of(client, "bob_shop") == expected


async def test_parallel_credits_into_a_brand_new_currency(
    client, merchant, transfer_body
):
    """Both transfers find no BTC balance for the receiver and try to open one;
    uq_merchant_currency must not turn that into a failed transfer."""
    await merchant("alice_store", currency="BTC", initial="10")
    await merchant("carol_co", currency="BTC", initial="10")
    await merchant("bob_shop", currency="USD", initial="0")

    responses = await asyncio.gather(
        *[
            client.post(
                "/transfers",
                json=transfer_body(sender, "bob_shop", "1"),
                headers={"Idempotency-Key": f"open-{sender}"},
            )
            for sender in ("alice_store", "carol_co")
        ]
    )

    assert {r.status_code for r in responses} == {201}
    assert await balance_of(client, "bob_shop", "BTC") == Decimal("2")
