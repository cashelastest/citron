from decimal import Decimal


class DomainError(Exception):
    """Base class for all domain-level errors."""
    error_code: str = "domain_error"
    status_code: int = 400

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class MerchantNotFoundError(DomainError):
    error_code = "merchant_not_found"
    status_code = 404

    def __init__(self, merchant_name: str):
        super().__init__(
            f"Merchant '{merchant_name}' not found",
            details={"merchant_name": merchant_name},
        )


class MerchantAlreadyExistsError(DomainError):
    error_code = "merchant_already_exists"
    status_code = 409

    def __init__(self, merchant_name: str):
        super().__init__(
            f"Merchant '{merchant_name}' already exists",
            details={"merchant_name": merchant_name},
        )


class BalanceNotFoundError(DomainError):
    error_code = "balance_not_found"
    status_code = 404

    def __init__(self, merchant_id, currency: str):
        super().__init__(
            f"No balance in {currency} for merchant {merchant_id}",
            details={"merchant_id": str(merchant_id), "currency": currency},
        )


class InsufficientFundsError(DomainError):
    error_code = "insufficient_funds"
    status_code = 402

    def __init__(self, merchant_id, currency: str, required: Decimal, available: Decimal):
        super().__init__(
            f"Insufficient funds: required {required} {currency}, available {available} {currency}",
            details={
                "merchant_id": str(merchant_id),
                "currency": currency,
                "required": str(required),
                "available": str(available),
            },
        )


class InvalidIdempotencyKeyError(DomainError):
    error_code = "invalid_idempotency_key"
    status_code = 400

    def __init__(self, reason: str):
        super().__init__(f"Invalid idempotency key: {reason}")


class DuplicateIdempotencyKeyError(DomainError):
    """A parallel request with the same key committed first.

    Internal signal: TransferService catches it and returns the winning transfer,
    so it should never reach the client. The status code is only a safety net.
    """
    error_code = "duplicate_idempotency_key"
    status_code = 409

    def __init__(self, idempotency_key: str):
        super().__init__(
            f"Idempotency key '{idempotency_key}' is already used",
            details={"idempotency_key": idempotency_key},
        )


class InvalidFeeConfigurationError(DomainError):
    """Service misconfiguration, not a client mistake — hence 500."""
    error_code = "invalid_fee_configuration"
    status_code = 500

    def __init__(self, fee_percent: Decimal):
        super().__init__(
            f"Fee percent must be in [0, 1), got {fee_percent}",
            details={"fee_percent": str(fee_percent)},
        )


class SameMerchantTransferError(DomainError):
    error_code = "same_merchant_transfer"
    status_code = 400

    def __init__(self, merchant_name: str):
        super().__init__(
            f"Cannot transfer to the same merchant: '{merchant_name}'",
            details={"merchant_name": merchant_name},
        )