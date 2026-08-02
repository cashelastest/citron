from decimal import Decimal, ROUND_HALF_UP

from app.domain.exceptions import InvalidFeeConfigurationError


class FeeCalculator:
    """Percentage fee charged to the sender on top of the transfer amount.

    Kept out of TransferService so the fee policy can be swapped (flat fee,
    per-currency rates, min/max caps) without touching the transfer flow.
    """

    SCALE = Decimal("0.00000001")

    def __init__(self, fee_percent: Decimal):
        if not (Decimal("0") <= fee_percent < Decimal("1")):
            raise InvalidFeeConfigurationError(fee_percent)
        self.fee_percent = fee_percent

    def calculate(self, amount: Decimal) -> Decimal:
        return (amount * self.fee_percent).quantize(self.SCALE, rounding=ROUND_HALF_UP)
