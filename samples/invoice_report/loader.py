import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Order:
    order_id: str
    customer: str
    country: str
    unit_price: float
    quantity: int
    discount_code: str


def load_orders(path: Path) -> list[Order]:
    with path.open(newline="", encoding="utf-8") as file:
        return [parse_row(row) for row in csv.DictReader(file)]


def parse_row(row: dict[str, str]) -> Order:
    return Order(
        order_id=row["order_id"],
        customer=row["customer"].strip(),
        country=row["country"].upper(),
        unit_price=float(row["unit_price"]),
        quantity=int(row["quantity"]),
        discount_code=row["discount_code"].strip(),
    )
