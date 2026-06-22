#!/usr/bin/env python
"""
Risk Parity Monitor — portfolio drift check.

Connects to IB Gateway, computes risk-parity target weights from IB
historical data, then values the current portfolio from ib.portfolio()
marketPrice/marketValue (last-known prices — valid out of hours, unlike
streaming tickers). Writes the snapshot to state.json and sends a phone
notification (via ntfy.sh) whenever any position drifts beyond the
configured threshold.

Two run modes:
    # long-lived: one check, then every CHECK_INTERVAL_SECS (interactive)
    python ibkr_stuff/risk_parity_monitor.py

    # single check then exit, for the daily systemd timer (ib-risk-parity)
    python ibkr_stuff/risk_parity_monitor.py --once

In --once mode the "monitor started" notification is suppressed (so the
daily timer doesn't add a second push) and the process exits non-zero if it can't
connect or value the portfolio — surfacing a logged-out gateway as a
systemd `failed` state, the same way snapshot_positions.py does.
"""

import argparse
import json
import logging
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from ib_async import IB, util

from config import (
    IB_HOST, IB_PORT, IB_CLIENT_ID, TRADING_MODE,
    DRIFT_THRESHOLD_PCT, CHECK_INTERVAL_SECS,
)
from notify import send as notify
from risk_parity_calc import get_risk_parity_weights

STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rp-monitor")


# ── helpers ──────────────────────────────────────────────────────────

def _write_state(account: str, positions: list[dict], total_value: float) -> None:
    """Atomically write the latest portfolio snapshot to state.json."""
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "account": account,
        "trading_mode": TRADING_MODE,
        "total_value": round(total_value, 2),
        "positions": positions,
    }
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, STATE_PATH)


def _format_drift_report(drifts: list[dict]) -> str:
    """Build a human-readable notification body from a list of drift dicts."""
    lines = ["Portfolio drift detected:\n"]
    for d in drifts:
        direction = "BUY" if d["diff"] < 0 else "SELL"
        lines.append(
            f"  {d['symbol']}: {d['actual']:.1f}% vs target {d['target']:.1f}% "
            f"(off by {abs(d['diff']):.1f}%) → {direction} ~${abs(d['dollar']):.0f}"
        )
    return "\n".join(lines)


# ── core logic ───────────────────────────────────────────────────────

def run(once: bool = False):
    ib = IB()

    # ── connect ──────────────────────────────────────────────────────
    log.info("Connecting to IB Gateway (%s:%s, mode=%s) …", IB_HOST, IB_PORT, TRADING_MODE)
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=15)
    except Exception as e:
        # Gateway down / logged out: exit non-zero so the systemd unit goes
        # `failed` and Netdata alarms — same contract as snapshot_positions.py.
        log.error("Could not connect to %s:%s (gateway down / logged out?) — %s", IB_HOST, IB_PORT, e)
        sys.exit(1)
    account = ib.managedAccounts()[0]
    log.info("Connected — account %s", account)

    # ── positions ────────────────────────────────────────────────────
    positions = ib.positions()
    if not positions:
        log.error("No open positions — nothing to monitor.")
        ib.disconnect()
        return

    # Map symbol → (contract, quantity)
    pos_map: dict[str, dict] = {}
    for pos in positions:
        sym = pos.contract.symbol
        pos_map[sym] = {"contract": pos.contract, "qty": float(pos.position)}

    tickers_list = sorted(pos_map.keys())
    log.info("Positions: %s", ", ".join(f"{s} ({pos_map[s]['qty']:.0f})" for s in tickers_list))

    # ── market valuation source ──────────────────────────────────────
    # Value positions from ib.portfolio() marketPrice/marketValue, NOT from
    # streaming reqMktData tickers. Portfolio values carry the last-known
    # price and stay valid with delayed data or markets closed; streaming
    # tickers return IB's -1 "no data" sentinel out of hours, which used to
    # poison the drift math (negative total value, bogus rebalance alerts).
    # IB pushes updatePortfolio automatically once connected — give it a
    # moment to populate before the first check.
    ib.reqMarketDataType(3)  # prefer delayed over nothing if real-time isn't subscribed
    for _ in range(10):
        if ib.portfolio():
            break
        ib.sleep(1)

    # ── target weights (computed once) ───────────────────────────────
    log.info("Computing risk-parity target weights (IB historical data) …")
    contracts = [pos_map[sym]["contract"] for sym in tickers_list]
    target_weights = get_risk_parity_weights(ib, contracts)
    for sym in tickers_list:
        log.info("  %s  target=%.2f%%", sym, target_weights[sym] * 100)

    if not once:
        # A one-shot timer run shouldn't fire a "started" push on every run —
        # only the rebalance alert below should notify.
        notify(
            "Risk parity monitor started — "
            + ", ".join(f"{s} {target_weights[s]*100:.1f}%" for s in tickers_list),
            title="RP Monitor",
        )

    # ── drift check ──────────────────────────────────────────────────
    if once:
        log.info("Single drift check (--once), threshold %.1f%%.", DRIFT_THRESHOLD_PCT)
    else:
        log.info(
            "Monitoring every %ds (drift threshold %.1f%%). Ctrl+C to stop.",
            CHECK_INTERVAL_SECS, DRIFT_THRESHOLD_PCT,
        )

    def check_drift():
        total_value = 0.0
        prices: dict[str, float] = {}
        holdings: dict[str, float] = {}

        # Snapshot current marketPrice / marketValue per position from IB.
        items = {it.contract.symbol: it for it in ib.portfolio()}
        for sym in tickers_list:
            item = items.get(sym)
            price = getattr(item, "marketPrice", None) if item else None
            if price is None or price <= 0 or math.isnan(price):
                log.warning("  %s — no valid price, skipping check", sym)
                return False
            prices[sym] = price
            holdings[sym] = item.marketValue  # qty × marketPrice, computed by IB
            total_value += item.marketValue

        if total_value <= 0:
            log.warning("Total portfolio value is %.2f — skipping check", total_value)
            return False

        drifts: list[dict] = []
        state_positions: list[dict] = []
        for sym in tickers_list:
            actual_pct = (holdings[sym] / total_value) * 100
            target_pct = target_weights[sym] * 100
            diff = actual_pct - target_pct
            state_positions.append({
                "symbol": sym,
                "quantity": pos_map[sym]["qty"],
                "price": round(prices[sym], 4),
                "market_value": round(holdings[sym], 2),
                "weight_actual_pct": round(actual_pct, 2),
                "weight_target_pct": round(target_pct, 2),
                "drift_pct": round(diff, 2),
            })
            if abs(diff) > DRIFT_THRESHOLD_PCT:
                drifts.append({
                    "symbol": sym,
                    "actual": actual_pct,
                    "target": target_pct,
                    "diff": diff,
                    "dollar": (diff / 100) * total_value,
                })
            log.info("  %s  actual=%.1f%%  target=%.1f%%  diff=%+.1f%%", sym, actual_pct, target_pct, diff)

        _write_state(account, state_positions, total_value)

        if drifts:
            log.warning("Drift threshold breached for %d position(s)", len(drifts))
            notify(_format_drift_report(drifts), title="Rebalance Needed", priority=4, tags="warning")
        else:
            log.info("All positions within %.1f%% tolerance ✓", DRIFT_THRESHOLD_PCT)

        return True

    if once:
        ok = check_drift()
        ib.disconnect()
        log.info("Disconnected.")
        sys.exit(0 if ok else 1)

    try:
        while True:
            check_drift()
            ib.sleep(CHECK_INTERVAL_SECS)
    except KeyboardInterrupt:
        log.info("Shutting down …")
    finally:
        ib.disconnect()
        log.info("Disconnected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Risk-parity portfolio drift check.")
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single drift check and exit (for the daily systemd timer).")
    args = parser.parse_args()
    run(once=args.once)
