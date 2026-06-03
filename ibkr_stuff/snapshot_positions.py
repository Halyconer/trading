#!/usr/bin/env python
"""Write a timestamped snapshot of current IBKR positions to positions.md.

Designed to run on a schedule (hourly cron). Connects to the IB Gateway
socket API (same config.py settings as check_positions.py) and overwrites
positions.md with a fresh table + "Last updated" timestamp.

Resilience: if the gateway is logged out (e.g. between IBKR's weekly forced
logout and the next 2FA approval), the connection fails and we DELIBERATELY
leave the existing positions.md untouched — so you always keep the last-known
snapshot, and the stale timestamp tells you it didn't refresh. Exits non-zero
on failure so cron logs show it, without clobbering good data.

Uses a dedicated clientId (9) so it never collides with an interactive
check_positions.py run (clientId 1).

Run from the repo root:  ./.venv/bin/python ibkr_stuff/snapshot_positions.py
"""

import sys
from datetime import datetime
from pathlib import Path

from ib_async import IB
from config import IB_HOST, IB_PORT, TRADING_MODE

SNAPSHOT_CLIENT_ID = 9
OUTPUT = Path(__file__).resolve().parent.parent / "positions.md"

try:
    from zoneinfo import ZoneInfo
    NOW = datetime.now(ZoneInfo("America/New_York"))
    TS = NOW.strftime("%Y-%m-%d %H:%M %Z")
except Exception:
    TS = datetime.now().strftime("%Y-%m-%d %H:%M (local)")


def build_markdown(portfolio, positions):
    lines = ["# IBKR Positions", "",
             f"_Last updated: **{TS}** ({TRADING_MODE} mode)_", ""]
    if portfolio:
        lines += ["| Symbol | Qty | Avg Cost | Mkt Price | Mkt Value | uPnL |",
                  "|---|---:|---:|---:|---:|---:|"]
        total_value = total_pnl = 0.0
        for p in sorted(portfolio, key=lambda x: x.contract.symbol):
            total_value += p.marketValue
            total_pnl += p.unrealizedPNL
            lines.append(
                f"| {p.contract.symbol} | {p.position:.0f} | {p.averageCost:.2f} "
                f"| {p.marketPrice:.2f} | {p.marketValue:.2f} | {p.unrealizedPNL:+.2f} |")
        lines.append(
            f"| **TOTAL** | | | | **{total_value:.2f}** | **{total_pnl:+.2f}** |")
    elif positions:
        lines += ["_(no market valuation available — holdings only)_", "",
                  "| Symbol | Qty | Avg Cost |", "|---|---:|---:|"]
        for p in sorted(positions, key=lambda x: x.contract.symbol):
            lines.append(f"| {p.contract.symbol} | {p.position:.0f} | {p.avgCost:.2f} |")
    else:
        lines.append("_No positions found for the connected account._")
    return "\n".join(lines) + "\n"


def main():
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=SNAPSHOT_CLIENT_ID, timeout=15)
    except Exception as e:
        # Leave the existing snapshot in place; just report and bail.
        print(f"{TS}: could not connect to {IB_HOST}:{IB_PORT} "
              f"(gateway down / logged out?) — keeping previous positions.md: {e}",
              file=sys.stderr)
        sys.exit(1)

    try:
        ib.sleep(1)  # let the account-update stream populate
        OUTPUT.write_text(build_markdown(ib.portfolio(), ib.positions()))
        print(f"{TS}: wrote {OUTPUT}")
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
