"""The order-processing flow. Every important step is a traced operation.

process_order
├── request.received          parse the raw request into an Order
├── validate_order            check the input
│   └── repository.get_product (one per item)
├── pricing.calculate_total
│   └── repository.get_product (one per item)
├── inventory.reserve_stock   (one per item)
├── payment.charge
└── order.confirm
    └── repository.save_order
"""

from typing import Any

from examples.order_service.errors import InvalidOrderError
from examples.order_service.inventory import Inventory
from examples.order_service.models import Order, OrderItem, OrderResult
from examples.order_service.payment import PaymentGateway
from examples.order_service.repository import ProductRepository
from tracer import set_attribute, traced

MAX_QUANTITY_PER_ITEM = 10
DISCOUNTS = {"SAVE10": 10}  # code -> percent


class OrderService:
    def __init__(self, repository: ProductRepository, inventory: Inventory, payments: PaymentGateway):
        self.repository = repository
        self.inventory = inventory
        self.payments = payments

    @traced("process_order")
    def process_order(self, payload: dict[str, Any]) -> OrderResult:
        set_attribute("order_id", payload.get("order_id"))
        order = self.receive_request(payload)
        set_attribute("item_count", len(order.items))
        self.validate_order(order)
        total = self.calculate_total(order)
        for item in order.items:
            self.inventory.reserve_stock(item.sku, item.quantity)
        payment_id = self.payments.charge(order.card_token, total)
        result = OrderResult(
            order_id=order.order_id,
            total_cents=total,
            payment_id=payment_id,
            reserved={i.sku: i.quantity for i in order.items},
        )
        self.confirm(result)
        set_attribute("total_cents", total)
        return result

    @traced("request.received")
    def receive_request(self, payload: dict[str, Any]) -> Order:
        set_attribute("field_count", len(payload))
        try:
            items = [OrderItem(sku=str(i["sku"]), quantity=int(i["quantity"])) for i in payload.get("items", [])]
            return Order(
                order_id=str(payload["order_id"]),
                customer_id=str(payload["customer_id"]),
                items=items,
                card_token=str(payload["card_token"]),
                discount_code=payload.get("discount_code"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidOrderError(f"Malformed order request: {exc!r}") from exc

    @traced("validate_order")
    def validate_order(self, order: Order) -> None:
        set_attribute("order_id", order.order_id)
        if not order.items:
            raise InvalidOrderError("Order must contain at least one item")
        for item in order.items:
            if not 1 <= item.quantity <= MAX_QUANTITY_PER_ITEM:
                raise InvalidOrderError(
                    f"Quantity for {item.sku} must be between 1 and {MAX_QUANTITY_PER_ITEM}, got {item.quantity}"
                )
            self.repository.get_product(item.sku)
        if order.discount_code is not None and order.discount_code not in DISCOUNTS:
            raise InvalidOrderError(f"Unknown discount code {order.discount_code}")

    @traced("pricing.calculate_total")
    def calculate_total(self, order: Order) -> int:
        subtotal = 0
        for item in order.items:
            product = self.repository.get_product(item.sku)
            subtotal += product.price_cents * item.quantity
        percent = DISCOUNTS.get(order.discount_code or "", 0)
        total = subtotal - subtotal * percent // 100
        set_attribute("subtotal_cents", subtotal)
        set_attribute("discount_percent", percent)
        set_attribute("total_cents", total)
        return total

    @traced("order.confirm")
    def confirm(self, result: OrderResult) -> None:
        set_attribute("order_id", result.order_id)
        set_attribute("payment_id", result.payment_id)
        self.repository.save_order(result)
