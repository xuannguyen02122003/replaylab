"""In-memory product and order storage that simulates database latency."""

import time

from examples.order_service.errors import ProductNotFoundError
from examples.order_service.models import OrderResult, Product
from tracer import set_attribute, traced


class ProductRepository:
    def __init__(self, products: list[Product], latency_ms: float = 3.0):
        self._products = {p.sku: p for p in products}
        self._orders: dict[str, OrderResult] = {}
        self.latency_ms = latency_ms

    def _simulate_latency(self) -> None:
        time.sleep(self.latency_ms / 1000)

    @traced("repository.get_product")
    def get_product(self, sku: str) -> Product:
        set_attribute("sku", sku)
        set_attribute("latency_ms", self.latency_ms)
        self._simulate_latency()
        product = self._products.get(sku)
        set_attribute("found", product is not None)
        if product is None:
            raise ProductNotFoundError(f"Product {sku} does not exist")
        return product

    @traced("repository.save_order")
    def save_order(self, result: OrderResult) -> None:
        set_attribute("order_id", result.order_id)
        self._simulate_latency()
        self._orders[result.order_id] = result
