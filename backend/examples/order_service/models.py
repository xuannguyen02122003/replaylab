"""Plain data classes for the demo order service."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price_cents: int


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    items: list[OrderItem]
    card_token: str
    discount_code: str | None = None


@dataclass
class OrderResult:
    order_id: str
    total_cents: int
    payment_id: str
    reserved: dict[str, int] = field(default_factory=dict)
