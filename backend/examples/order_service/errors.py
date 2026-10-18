"""Business errors raised by the demo order service.

They all inherit from OrderError, so a scenario runner can tell
"expected business failure" apart from "bug in the code".
"""


class OrderError(Exception):
    """Base class for expected order-processing failures."""


class InvalidOrderError(OrderError):
    pass


class ProductNotFoundError(OrderError):
    pass


class OutOfStockError(OrderError):
    pass


class PaymentDeclinedError(OrderError):
    pass
