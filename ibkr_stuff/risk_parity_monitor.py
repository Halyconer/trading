#!/usr/bin/env python
"""
Risk Parity Monitor — live market data + hourly drift check.

Connects to IB Gateway, subscribes to streaming market data for all
positions, computes risk-parity target weights once at startup, then
checks portfolio drift every CHECK_INTERVAL_SECS.  Sends a phone
notification (via ntfy.sh) whenever any position drifts beyond the
configured threshold.

Usage:
    python ibkr_stuff/risk_parity_monitor.py
"""

import logging
import sys
import math

from ib_async import IB, util

from config import (
    IB_HOST, IB_PORT, IB_CLIENT_ID, TRADING_MODE,
    DRIFT_THRESHOLD_PCT, CHECK_INTERVAL_SECS,
)
from notify import send as notify
from risk_parity_calc import get_risk_parity_weights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rp-monitor")


# ── helpers ──────────────────────────────────────────────────────────

def _best_price(ticker) -> float | None:
    """Return the best available price from a live ticker object."""
    for attr in ("last", "close", "bid"):
        val = getattr(ticker, attr, None)
        if val is not None and not math.isnan(val):
            return val
    return None


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

def run():
    ib = IB()

    # ── connect ──────────────────────────────────────────────────────
    log.info("Connecting to IB Gateway (%s:%s, mode=%s) …", IB_HOST, IB_PORT, TRADING_MODE)
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
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

    # ── subscribe to live market data ────────────────────────────────
    log.info("Subscribing to live market data …")
    ib.reqMarketDataType(3)  # delayed if live unavailable
    live_tickers: dict[str, object] = {}
    for sym in tickers_list:
        contract = pos_map[sym]["contract"]
        ticker = ib.reqMktData(contract, "", False, False)  # snapshot=False → streaming
        live_tickers[sym] = ticker

    # Wait for all prices to populate
    max_wait = 30
    waited = 0
    while waited < max_wait:
        ib.sleep(1)
        waited += 1
        missing = [s for s in tickers_list if _best_price(live_tickers[s]) is None]
        if not missing:
            break
        if waited % 5 == 0:
            log.info("Waiting for prices: %s (%ds/%ds)", ", ".join(missing), waited, max_wait)

    for sym in tickers_list:
        price = _best_price(live_tickers[sym])
        if price:
            log.info("  %s  price=%.2f", sym, price)
        else:
            log.warning("  %s  price still unavailable after %ds", sym, max_wait)

    # ── target weights (computed once) ───────────────────────────────
    log.info("Computing risk-parity target weights (IB historical data) …")
    contracts = [pos_map[sym]["contract"] for sym in tickers_list]
    target_weights = get_risk_parity_weights(ib, contracts)
    for sym in tickers_list:
        log.info("  %s  target=%.2f%%", sym, target_weights[sym] * 100)

    notify(
        "Risk parity monitor started — "
        + ", ".join(f"{s} {target_weights[s]*100:.1f}%" for s in tickers_list),
        title="RP Monitor",
    )

    # ── periodic drift check ─────────────────────────────────────────
    log.info(
        "Monitoring every %ds (drift threshold %.1f%%). Ctrl+C to stop.",
        CHECK_INTERVAL_SECS, DRIFT_THRESHOLD_PCT,
    )

    def check_drift():
        total_value = 0.0
        holdings: dict[str, float] = {}

        for sym in tickers_list:
            price = _best_price(live_tickers[sym])
            if price is None:
                log.warning("  %s — no price yet, skipping check", sym)
                return
            mv = pos_map[sym]["qty"] * price
            holdings[sym] = mv
            total_value += mv

        if total_value == 0:
            log.warning("Total portfolio value is 0 — skipping check")
            return

        drifts: list[dict] = []
        for sym in tickers_list:
            actual_pct = (holdings[sym] / total_value) * 100
            target_pct = target_weights[sym] * 100
            diff = actual_pct - target_pct
            if abs(diff) > DRIFT_THRESHOLD_PCT:
                drifts.append({
                    "symbol": sym,
                    "actual": actual_pct,
                    "target": target_pct,
                    "diff": diff,
                    "dollar": (diff / 100) * total_value,
                })
            log.info("  %s  actual=%.1f%%  target=%.1f%%  diff=%+.1f%%", sym, actual_pct, target_pct, diff)

        if drifts:
            log.warning("Drift threshold breached for %d position(s)", len(drifts))
            notify(_format_drift_report(drifts), title="Rebalance Needed", priority=4, tags="warning")
        else:
            log.info("All positions within %.1f%% tolerance ✓", DRIFT_THRESHOLD_PCT)

    try:
        while True:
            check_drift()
            ib.sleep(CHECK_INTERVAL_SECS)
    except KeyboardInterrupt:
        log.info("Shutting down …")
    finally:
        # Cancel market data subscriptions
        for sym in tickers_list:
            ib.cancelMktData(pos_map[sym]["contract"])
        ib.disconnect()
        log.info("Disconnected.")


if __name__ == "__main__":
    run()
