"""Pure unit tests — no database, no HTTP."""
from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidFeeConfigurationError
from app.domain.services.fee_calculator import FeeCalculator


@pytest.mark.parametrize(
    ("percent", "amount", "expected"),
    [
        ("0.01", "0.000005", "0.00000005"),
        ("0.01", "100", "1.00000000"),
        ("0", "100", "0.00000000"),
        ("0.025", "100", "2.50000000"),
        ("0.5", "0.00000003", "0.00000002"),
        ("0.01", "0.00000001", "0.00000000"),
    ],
)
def test_fee_is_quantised_to_eight_decimals(percent, amount, expected):
    fee = FeeCalculator(Decimal(percent)).calculate(Decimal(amount))
    assert fee == Decimal(expected)
    assert fee.as_tuple().exponent == -8


@pytest.mark.parametrize("percent", ["-0.01", "1", "1.5"])
def test_rejects_fee_percent_outside_range(percent):
    with pytest.raises(InvalidFeeConfigurationError) as exc_info:
        FeeCalculator(Decimal(percent))

    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == "invalid_fee_configuration"
