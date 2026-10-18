"""Stock levels and reservations."""

import time

from examples.order_service.errors import OutOfStockError
from tracer import set_attribute, traced


class Inventory:
    def __init__(self, stock: dict[str, int]):
        self._stock = dict(stock)

    @traced("inventory.reserve_stock")
    def reserve_stock(self, sku: str, quantity: int) -> None:
        available = self._stock.get(sku, 0)
        set_attribute("sku", sku)
        set_attribute("requested", quantity)
        set_attribute("available", available)
        time.sleep(0.002)
        if available < quantity:
            raise OutOfStockError(f"Product {sku} has {available} units available, {quantity} requested")
        self._stock[sku] = available - quantity

    def available(self, sku: str) -> int:
        return self._stock.get(sku, 0)
