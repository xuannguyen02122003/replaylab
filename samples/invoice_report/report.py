from pricing import PricedOrder


def print_report(orders: list[PricedOrder]) -> None:
    print(f"{'Order':<8} {'Customer':<12} {'Total':>10}")
    for priced in orders:
        print(format_line(priced))
    print(f"{'':<21}{'-' * 10}")
    print(f"{'Grand total':<21}{grand_total(orders):>10.2f}")


def format_line(priced: PricedOrder) -> str:
    return f"{priced.order.order_id:<8} {priced.order.customer:<12} {priced.total:>10.2f}"


def grand_total(orders: list[PricedOrder]) -> float:
    return round(sum(p.total for p in orders), 2)
