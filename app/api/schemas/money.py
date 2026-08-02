from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer, StringConstraints

MONEY_SCALE = Decimal("0.00000001")

CurrencyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=3,
        max_length=10,
        # Case-insensitive on purpose: pydantic checks the pattern against the
        # raw input, before to_upper runs, so ^[A-Z0-9]+$ would reject "btc".
        pattern=r"^[A-Za-z0-9]+$",
    ),
]
"""Normalised at the edge: without to_upper, "btc" and "BTC" would end up as two
independent balances for the same merchant, since uq_merchant_currency compares
the raw string."""


def _format(amount: Decimal) -> str:
    """Fixed 8 decimals, never scientific notation.

    str(Decimal("5E-8")) is "5E-8" — correct arithmetic, unusable as a money
    string. Quantizing also keeps the scale identical whether the value was
    just built in memory or read back from Numeric(20, 8).
    """
    return f"{amount.quantize(MONEY_SCALE):f}"


Money = Annotated[Decimal, PlainSerializer(_format, return_type=str, when_used="json")]
