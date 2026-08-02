from decimal import Decimal

from tests.conftest import balance_of


async def test_create_merchant_returns_initial_balance(client):
    response = await client.post(
        "/merchants",
        json={
            "merchant_name": "alice_store",
            "currency": "BTC",
            "initial_balance": "0.00001",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["merchant_name"] == "alice_store"
    assert body["balances"] == [{"currency": "BTC", "amount": "0.00001000"}]


async def test_duplicate_merchant_is_rejected(client, merchant):
    await merchant("alice_store")

    response = await client.post(
        "/merchants",
        json={"merchant_name": "alice_store", "currency": "BTC", "initial_balance": "0"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "merchant_already_exists"


async def test_get_merchant(client, merchant):
    await merchant("alice_store", initial="2.5")

    response = await client.get("/merchants/alice_store")

    assert response.status_code == 200
    assert response.json()["balances"] == [{"currency": "BTC", "amount": "2.50000000"}]


async def test_get_unknown_merchant_is_404(client):
    response = await client.get("/merchants/nobody")

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "merchant_not_found"
    assert body["details"] == {"merchant_name": "nobody"}


async def test_balance_endpoint_lists_every_currency(client, merchant, transfer_body):
    await merchant("alice_store", currency="BTC", initial="1")
    await merchant("bob_shop", currency="USD", initial="0")
    await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "0.5"),
        headers={"Idempotency-Key": "multi-currency"},
    )

    response = await client.get("/merchants/bob_shop/balance")

    assert response.status_code == 200
    assert sorted(response.json(), key=lambda b: b["currency"]) == [
        {"currency": "BTC", "amount": "0.50000000"},
        {"currency": "USD", "amount": "0.00000000"},
    ]


async def test_invalid_input_is_422_with_structured_body(client):
    response = await client.post(
        "/merchants",
        json={"merchant_name": "", "currency": "B", "initial_balance": "-1"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert {e["loc"][-1] for e in body["details"]["errors"]} == {
        "merchant_name",
        "currency",
        "initial_balance",
    }


async def test_currency_is_normalised_to_upper_case(client, merchant, transfer_body):
    """Otherwise "btc" and "BTC" become two independent balances."""
    await client.post(
        "/merchants",
        json={"merchant_name": "alice_store", "currency": " btc ", "initial_balance": "1"},
    )
    await merchant("bob_shop")

    response = await client.post(
        "/transfers",
        json=transfer_body("alice_store", "bob_shop", "0.1", currency="Btc"),
        headers={"Idempotency-Key": "case-insensitive"},
    )

    assert response.status_code == 201
    assert response.json()["currency"] == "BTC"
    assert await balance_of(client, "alice_store") == Decimal("0.899")
