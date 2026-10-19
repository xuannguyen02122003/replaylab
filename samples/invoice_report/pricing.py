from dataclasses import dataclass

from loader import Order

TAX_RATES = {"VN": 0.10, "AU": 0.10, "SG": 0.09, "US": 0.0}
DISCOUNTS = {"": 0.0, "STUDENT": 0.15, "VIP": 0.25}


@dataclass
class PricedOrder:
    order: Order
    subtotal: float
    discount: float
    tax: float
    total: float


def price_order(order: Order) -> PricedOrder:
    subtotal = order.unit_price * order.quantity
    discount = apply_discount(subtotal, order.discount_code)
    tax = tax_for(order.country, subtotal - discount)
    return PricedOrder(order, subtotal, discount, tax, round(subtotal - discount + tax, 2))


def apply_discount(amount: float, code: str) -> float:
    return round(amount * DISCOUNTS[code], 2)  # unknown code -> KeyError


def tax_for(country: str, amount: float) -> float:
    return round(amount * TAX_RATES.get(country, 0.0), 2)
