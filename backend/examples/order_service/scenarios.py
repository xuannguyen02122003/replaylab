"""Predefined demo scenarios. Each one runs the real order service under the tracer.

Only these scenarios can be executed. ReplayLab never runs code that a user submits.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from examples.order_service.errors import OrderError
from examples.order_service.inventory import Inventory
from examples.order_service.models import Product
from examples.order_service.payment import DECLINED_TOKEN, PaymentGateway
from examples.order_service.repository import ProductRepository
from examples.order_service.service import OrderService
from tracer import Recorder, run

PRODUCTS = [
    Product(sku="SKU-100", name="Mechanical keyboard", price_cents=89_00),
    Product(sku="SKU-123", name="USB-C cable", price_cents=12_50),
    Product(sku="SKU-200", name="27-inch monitor", price_cents=249_00),
]


def _service(stock: dict[str, int], latency_ms: float = 3.0) -> OrderService:
    return OrderService(ProductRepository(PRODUCTS, latency_ms=latency_ms), Inventory(stock), PaymentGateway())


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "order_id": "ORD-1001",
        "customer_id": "CUS-42",
        "items": [{"sku": "SKU-100", "quantity": 1}, {"sku": "SKU-123", "quantity": 3}],
        "card_token": "tok_visa_4242",
    }
    payload.update(overrides)
    return payload


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    expected_status: str  # "ok" or "error"
    execute: Callable[[], Any]


SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in [
        Scenario(
            "order_success",
            "Two items in stock, valid card. The order is confirmed.",
            "ok",
            lambda: _service({"SKU-100": 5, "SKU-123": 10}).process_order(_payload()),
        ),
        Scenario(
            "order_with_discount",
            "Same order as order_success with the SAVE10 discount code.",
            "ok",
            lambda: _service({"SKU-100": 5, "SKU-123": 10}).process_order(_payload(discount_code="SAVE10")),
        ),
        Scenario(
            "order_out_of_stock",
            "SKU-123 has no stock left, so reserving it fails.",
            "error",
            lambda: _service({"SKU-100": 5, "SKU-123": 0}).process_order(_payload()),
        ),
        Scenario(
            "order_invalid_input",
            "A quantity of 0 fails input validation.",
            "error",
            lambda: _service({"SKU-100": 5}).process_order(_payload(items=[{"sku": "SKU-100", "quantity": 0}])),
        ),
        Scenario(
            "order_payment_declined",
            "Stock is reserved, then the card is declined.",
            "error",
            lambda: _service({"SKU-100": 5, "SKU-123": 10}).process_order(_payload(card_token=DECLINED_TOKEN)),
        ),
        Scenario(
            "order_slow_repository",
            "Same as order_success, but the database is 20x slower.",
            "ok",
            lambda: _service({"SKU-100": 5, "SKU-123": 10}, latency_ms=60.0).process_order(_payload()),
        ),
    ]
}


def run_scenario(name: str) -> Recorder:
    """Execute one scenario under the tracer and return its recorder.

    Expected business errors (OrderError) are recorded and then swallowed,
    because a failing order is a valid scenario outcome. Any other exception
    is a real bug and is re-raised.
    """
    scenario = SCENARIOS[name]
    try:
        with run(name, attributes={"expected_status": scenario.expected_status}) as recorder:
            scenario.execute()
    except OrderError:
        pass
    return recorder
