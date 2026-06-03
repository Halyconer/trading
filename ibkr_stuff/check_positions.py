#!/usr/bin/env python
"""Check current positions in your IBKR account (socket API via IB Gateway).

Connects to the IB Gateway / TWS socket API defined in config.py
(IB_HOST, IB_PORT, IB_CLIENT_ID) — e.g. the gnzsnz ib-gateway container on the
Pi at 192.168.0.73:4002 (paper) or :4001 (live). Positions belong to whichever
account the gateway is logged into, so to see *live* positions the gateway must
be running in live mode (IB_PORT=4001).

Usage:
    python ibkr_stuff/check_positions.py            # all positions
    python ibkr_stuff/check_positions.py AZN NVDA   # filter to these symbols
"""

import sys
from ib_async import IB
from config import IB_HOST, IB_PORT, IB_CLIENT_ID, TRADING_MODE


def main():
    symbols = {s.upper() for s in sys.argv[1:]}

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
    except Exception as e:
        print(f"ERROR: could not connect to {IB_HOST}:{IB_PORT} (clientId={IB_CLIENT_ID})")
        print(f"  {e}")
        print("  Check: gateway container up and logged in? your IP in Trusted IPs?")
        sys.exit(1)

    print(f"Connected to {IB_HOST}:{IB_PORT} ({TRADING_MODE} mode)\n")

    # portfolio() carries valuation + P&L; positions() is the bare holdings.
    # Give the account-update stream a moment to populate after connect.
    ib.sleep(1)
    portfolio = ib.portfolio()
    positions = ib.positions()

    if symbols:
        portfolio = [p for p in portfolio if p.contract.symbol in symbols]
        positions = [p for p in positions if p.contract.symbol in symbols]

    if portfolio:
        header = f"{'Symbol':<8}{'Qty':>10}{'AvgCost':>12}{'MktPrice':>12}{'MktValue':>14}{'uPnL':>14}"
        print(header)
        print("-" * len(header))
        total_value = total_pnl = 0.0
        for p in sorted(portfolio, key=lambda x: x.contract.symbol):
            total_value += p.marketValue
            total_pnl += p.unrealizedPNL
            print(f"{p.contract.symbol:<8}{p.position:>10.2f}{p.averageCost:>12.2f}"
                  f"{p.marketPrice:>12.2f}{p.marketValue:>14.2f}{p.unrealizedPNL:>14.2f}")
        print("-" * len(header))
        print(f"{'TOTAL':<8}{'':>10}{'':>12}{'':>12}{total_value:>14.2f}{total_pnl:>14.2f}")
    elif positions:
        # portfolio empty (e.g. no market-data subscription) — show bare holdings.
        print("(no market valuation available — showing holdings only)\n")
        for p in sorted(positions, key=lambda x: x.contract.symbol):
            print(f"  {p.contract.symbol}: {p.position} @ avg {p.avgCost:.2f}")
    else:
        print("No positions found for the connected account.")

    ib.disconnect()


if __name__ == "__main__":
    main()
