#!/usr/bin/env python
"""
Mirror real account positions into paper account.

Places market orders on paper account to replicate positions.
Run during market hours so orders fill immediately.

Usage:
    python ibkr_stuff/mirror_positions.py          # dry run (default)
    python ibkr_stuff/mirror_positions.py --execute # actually place orders
"""

import sys
from ib_async import IB, Stock, MarketOrder
from config import IB_HOST, IB_PORT, IB_CLIENT_ID

# Target positions to replicate
# Fractional shares are flagged — IBKR API doesn't support them.
# You'll need to round or buy those manually via the app.
POSITIONS = [
    # (symbol, quantity, exchange)
    ("ASML", 0.67, "SMART"),   # fractional — will skip
    ("AZN", 0.25, "SMART"),    # fractional — will skip
    ("B", 30, "SMART"),
    ("DIA", 1, "SMART"),
    ("GLD", 1, "SMART"),
    ("GOOGL", 2.5, "SMART"),   # fractional — will skip
    ("MSFT", 1, "SMART"),
    ("NVDA", 4, "SMART"),
    ("QQQ", 0.3, "SMART"),     # fractional — will skip
    ("SLV", 5, "SMART"),
    ("TSM", 3, "SMART"),
    ("VEU", 10, "SMART"),
    ("VGK", 5, "SMART"),
    ("VTV", 5, "SMART"),
]


def get_existing_positions(ib):
    """Get dict of symbol -> quantity for current paper positions."""
    return {pos.contract.symbol: pos.position for pos in ib.positions()}


def main():
    execute = "--execute" in sys.argv

    if not execute:
        print("DRY RUN — pass --execute to place orders\n")

    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
    print(f"Connected to paper account on port {IB_PORT}\n")

    existing = get_existing_positions(ib)
    if existing:
        print("Current paper positions:")
        for sym, qty in existing.items():
            print(f"  {sym}: {qty}")
        print()

    skipped = []
    to_order = []

    for symbol, qty, exchange in POSITIONS:
        # Check if fractional
        if qty != int(qty):
            skipped.append((symbol, qty, "fractional — buy manually in app"))
            continue

        qty = int(qty)

        # Adjust for existing positions
        already_have = int(existing.get(symbol, 0))
        needed = qty - already_have

        if needed <= 0:
            skipped.append((symbol, qty, f"already have {already_have}"))
            continue

        to_order.append((symbol, needed, exchange))

    # Show plan
    if to_order:
        print("Orders to place:")
        for symbol, qty, exchange in to_order:
            print(f"  BUY {qty} {symbol}")
        print()

    if skipped:
        print("Skipped:")
        for symbol, qty, reason in skipped:
            print(f"  {symbol} ({qty}) — {reason}")
        print()

    if not to_order:
        print("Nothing to order.")
        ib.disconnect()
        return

    if not execute:
        print("Run with --execute to place these orders.")
        ib.disconnect()
        return

    # Place orders
    for symbol, qty, exchange in to_order:
        contract = Stock(symbol, exchange, "USD")
        ib.qualifyContracts(contract)
        order = MarketOrder("BUY", qty)

        print(f"Placing: BUY {qty} {symbol}...", end=" ")
        trade = ib.placeOrder(contract, order)
        ib.sleep(1)
        print(f"status={trade.orderStatus.status}")

    # Wait for fills
    print("\nWaiting for fills...")
    ib.sleep(5)

    # Show final state
    print("\nFinal paper positions:")
    for pos in ib.positions():
        print(f"  {pos.contract.symbol}: {pos.position} @ {pos.avgCost:.2f}")

    ib.disconnect()
    print("\nDone.")


if __name__ == "__main__":
    main()
