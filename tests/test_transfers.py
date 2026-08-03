from decimal import Decimal

import pytest

from tests.conftest import balance_of


async def test_sender_pays_fee_receiver_gets_exact_amount(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "0.1"),
        headers={"Idempotency-Key": "abc-123-xyz"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "0.10000000"
    assert body["fee_amount"] == "0.00100000"
    assert body["total_amount"] == "0.10100000"
    assert body["from_merchant"] == "alice_store"
    assert body["to_merchant"] == "bob_shop"

    assert await balance_of(client, "alice_store") == Decimal("0.899")
    assert await balance_of(client, "bob_shop") == Decimal("0.1")


async def test_small_amounts_never_serialise_in_scientific_notation(
    client, merchant, transfer_body
):
    """str(Decimal("5E-8")) is "5E-8"; a money API must not emit that."""
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "0.000005"),
        headers={"Idempotency-Key": "key"},
    )

    body = response.json()
    assert body["fee_amount"] == "0.00000005"
    assert body["total_amount"] == "0.00000505"
    assert "E" not in body["fee_amount"]


async def test_insufficient_funds_accounts_for_the_fee(client, merchant, transfer_body):
    """The balance covers the amount exactly — the fee is what breaks it."""
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "1"),
        headers={"Idempotency-Key": "just-over"},
    )

    assert response.status_code == 402
    body = response.json()
    assert body["error_code"] == "insufficient_funds"
    assert body["details"]["required"] == "1.01000000"
    assert body["details"]["available"] == "1.00000000"

    assert await balance_of(client, "alice_store") == Decimal("1")
    assert await balance_of(client, "bob_shop") == Decimal("0")


async def test_rejected_transfer_is_not_recorded(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")
    await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "999"),
        headers={"Idempotency-Key": "too-much"},
    )

    listing = await client.get("/transfers")

    assert listing.json() == []


async def test_receiver_without_that_currency_gets_a_new_balance(
    client, merchant, transfer_body
):
    await merchant("alice_store", currency="BTC", initial="1")
    await merchant("bob_shop", currency="USD", initial="0")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "0.25"),
        headers={"Idempotency-Key": "new-currency"},
    )

    assert response.status_code == 201
    assert await balance_of(client, "bob_shop", "BTC") == Decimal("0.25")
    assert await balance_of(client, "bob_shop", "USD") == Decimal("0")


async def test_sender_without_that_currency_is_rejected(client, merchant, transfer_body):
    """Opening a balance for the receiver is a convenience; spending from a
    non-existent account is not."""
    await merchant("alice_store", currency="USD", initial="100")
    await merchant("bob_shop", currency="BTC", initial="0")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "1", currency="BTC"),
        headers={"Idempotency-Key": "no-such-account"},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "balance_not_found"


async def test_transfer_to_self_is_rejected(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "alice_store", "0.1"),
        headers={"Idempotency-Key": "self"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "same_merchant_transfer"


async def test_unknown_merchant_is_rejected(client, merchant, transfer_body):
    await merchant("alice_store", initial="1")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "ghost", "0.1"),
        headers={"Idempotency-Key": "ghost"},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "merchant_not_found"


@pytest.mark.parametrize("amount", ["0", "-1", "abc"])
async def test_non_positive_amount_is_rejected(client, merchant, transfer_body, amount):
    await merchant("alice_store", initial="1")
    await merchant("bob_shop")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", amount),
        headers={"Idempotency-Key": f"bad-{amount}"},
    )

    assert response.status_code == 422


class TestIdempotencyKeyHeader:
    async def test_missing_header_is_rejected(self, client, merchant, transfer_body):
        await merchant("alice_store", initial="1")
        await merchant("bob_shop")

        response = await client.post(
            "/transfers", json=transfer_body("alice_store", "bob_shop", "0.1")
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "invalid_idempotency_key"

    async def test_blank_header_is_rejected(self, client, merchant, transfer_body):
        await merchant("alice_store", initial="1")
        await merchant("bob_shop")

        response = await client.post(
            "/transfers",
            json=transfer_body("alice_store", "bob_shop", "0.1"),
            headers={"Idempotency-Key": "   "},
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "invalid_idempotency_key"

    async def test_overlong_header_is_rejected(self, client, merchant, transfer_body):
        await merchant("alice_store", initial="1")
        await merchant("bob_shop")

        response = await client.post(
            "/transfers",
            json=transfer_body("alice_store", "bob_shop", "0.1"),
            headers={"Idempotency-Key": "k" * 256},
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "invalid_idempotency_key"


class TestListTransfers:
    @pytest.fixture(autouse=True)
    async def _seed(self, client, merchant, transfer_body):
        await merchant("alice_store", initial="10")
        await merchant("bob_shop")
        await merchant("carol_co", currency="USD", initial="50")
        await merchant("dave_ltd", currency="USD", initial="0")

        for key, sender, receiver, amount, currency in [
            ("t1", "alice_store", "bob_shop", "1", "BTC"),
            ("t2", "alice_store", "carol_co", "2", "BTC"),
            ("t3", "carol_co", "dave_ltd", "5", "USD"),
        ]:
            response = await client.post(
                "/transfers",
                json=transfer_body(sender, receiver, amount, currency),
                headers={"Idempotency-Key": key},
            )
            assert response.status_code == 201, response.text

    async def test_without_filters_returns_everything(self, client):
        response = await client.get("/transfers")

        assert response.status_code == 200
        assert len(response.json()) == 3
        # Names are joined in, not echoed back from the query string.
        assert all(t["from_merchant"] and t["to_merchant"] for t in response.json())

    async def test_filter_by_sender(self, client):
        response = await client.get("/transfers", params={"from": "alice_store"})

        assert len(response.json()) == 2

    async def test_filter_by_receiver(self, client):
        response = await client.get("/transfers", params={"to": "dave_ltd"})

        assert [t["to_merchant"] for t in response.json()] == ["dave_ltd"]

    async def test_filter_by_currency(self, client):
        response = await client.get("/transfers", params={"currency": "USD"})

        assert [t["currency"] for t in response.json()] == ["USD"]

    async def test_filters_combine(self, client):
        response = await client.get(
            "/transfers",
            params={"from": "alice_store", "to": "bob_shop", "currency": "BTC"},
        )

        assert len(response.json()) == 1

    async def test_unknown_merchant_in_filter_is_404(self, client):
        response = await client.get("/transfers", params={"from": "ghost"})

        assert response.status_code == 404
