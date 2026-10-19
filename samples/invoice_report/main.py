"""Invoice report: a small, ordinary Python project (no ReplayLab code inside).

    python main.py                  uses data/orders.csv
    python main.py path/to/file.csv
"""

import sys
from pathlib import Path

from loader import load_orders
from pricing import price_order
from report import print_report


def main(argv: list[str]) -> None:
    csv_path = Path(argv[1]) if len(argv) > 1 else Path(__file__).parent / "data" / "orders.csv"
    orders = load_orders(csv_path)
    priced = [price_order(order) for order in orders]
    print_report(priced)


if __name__ == "__main__":
    main(sys.argv)
