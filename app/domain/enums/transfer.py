from enum import Enum


class TransferStatus(Enum):
    NEW = "New"
    WAIT_PAYMENT = "Wait Payment"
    DONE = "Done"


    