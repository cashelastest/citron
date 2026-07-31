from fastapi import HTTPException


class MerchantNotFoundError(HTTPException):
    def __init__(self, merchant_name):
        super().__init__(status_code=404, detail=f"{merchant_name} not found")
