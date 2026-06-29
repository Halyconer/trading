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
    CASH_TICKERS, STOP_LOSS_PCT,
)
from notify import send as notify
from risk_parity_calc import fetch_price_frame, weights_from_prices

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


def _archive_snapshot() -> None:
    """
    Append the snapshot just written to state.json into the DuckDB warehouse, so
    a queryable history accumulates run-over-run. Best-effort: the warehouse is
    research storage, not part of the alerting contract, so any failure here
    (duckdb missing, disk issue) is logged and swallowed — it must never stop
    the drift / stop-loss alerts. Lazy import keeps duckdb off the critical path
    for clients that don't have it (e.g. the Mac).
    """
    try:
        from warehouse import connect, ingest_state
        con = connect()
        try:
            added = ingest_state(con)
        finally:
            con.close()
        log.info("Warehouse: +%d row(s) archived to DuckDB", added)
    except Exception as e:
        log.warning("Warehouse archive skipped (non-fatal): %s", e)


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


def _format_stop_report(stops: list[dict]) -> str:
    """Human-readable body for the stop-loss recommender alert."""
    lines = ["Positions down past your stop-loss vs cost — review:\n"]
    for s in stops:
        lines.append(
            f"  {s['symbol']}: down {s['loss']:.1f}% vs cost "
            f"(paid ${s['cost']:.2f}, now ${s['price']:.2f})"
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

    # ── target weights + stop-loss drawdowns (one history fetch) ─────
    # Cash-like tickers (CASH_TICKERS, e.g. SGOV) are kept OUT of the optimiser
    # — a near-zero-vol asset can't be equal-risk-sized and would otherwise get
    # a garbage target (the old "SELL SGOV" false alarm). Anything the optimiser
    # actually sized is the "managed" risk sleeve; everything else (cash, or an
    # asset IB had no history for) is pinned to its current weight in the drift
    # math below, so it never raises a bogus rebalance alert.
    log.info("Fetching IB history → risk-parity weights …")
    contracts = [pos_map[sym]["contract"] for sym in tickers_list]
    prices_hist = fetch_price_frame(ib, contracts, exclude=CASH_TICKERS)
    risky_weights = weights_from_prices(prices_hist)   # sums to 1 over the risky sleeve
    managed = set(risky_weights)
    pinned = [s for s in tickers_list if s not in managed]
    log.info("Risk-parity sleeve: %s", ", ".join(f"{s} {risky_weights[s]*100:.1f}%"
                                                  for s in sorted(managed)) or "none")
    if pinned:
        log.info("Pinned to current weight (cash / no history): %s", ", ".join(pinned))

    if not once:
        # A one-shot timer run shouldn't fire a "started" push on every run —
        # only the rebalance / stop-loss alerts below should notify.
        notify(
            "Risk parity monitor started — "
            + ", ".join(f"{s} {risky_weights[s]*100:.1f}%" for s in sorted(managed)),
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
        costs: dict[str, float] = {}

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
            costs[sym] = item.averageCost     # your entry price (per share/coin) — your lot
            total_value += item.marketValue

        if total_value <= 0:
            log.warning("Total portfolio value is %.2f — skipping check", total_value)
            return False

        # Pinned holdings (cash sleeve + any no-history asset) keep their current
        # weight; the risk-parity targets fill only the remaining budget, so the
        # two sets of targets add up to 100% and pinned assets show ~zero drift.
        pinned_value = sum(holdings[s] for s in tickers_list if s not in managed)
        risky_budget = max(0.0, 1 - pinned_value / total_value)

        drifts: list[dict] = []
        stops: list[dict] = []
        state_positions: list[dict] = []
        for sym in tickers_list:
            actual_pct = (holdings[sym] / total_value) * 100
            if sym in managed:
                target_pct = risky_weights[sym] * risky_budget * 100
            else:
                target_pct = actual_pct  # pinned: cash / no-data → no drift by design
            diff = actual_pct - target_pct

            # Loss against YOUR cost basis (the lot you actually bought), not a
            # market high you never traded at. Positive = underwater vs entry.
            cost = costs[sym]
            loss_pct = (cost - prices[sym]) / cost * 100 if cost > 0 else 0.0

            state_positions.append({
                "symbol": sym,
                "quantity": pos_map[sym]["qty"],
                "price": round(prices[sym], 4),
                "avg_cost": round(cost, 4),
                "market_value": round(holdings[sym], 2),
                "weight_actual_pct": round(actual_pct, 2),
                "weight_target_pct": round(target_pct, 2),
                "drift_pct": round(diff, 2),
                "loss_vs_cost_pct": round(loss_pct, 2),
            })
            if abs(diff) > DRIFT_THRESHOLD_PCT:
                drifts.append({
                    "symbol": sym,
                    "actual": actual_pct,
                    "target": target_pct,
                    "diff": diff,
                    "dollar": (diff / 100) * total_value,
                })
            # Stop-loss recommender: flag a risky holding now down more than
            # STOP_LOSS_PCT from your average cost. Cash/pinned assets are
            # exempt. This only *alerts* — it never places an order.
            if STOP_LOSS_PCT > 0 and sym in managed and loss_pct >= STOP_LOSS_PCT:
                stops.append({"symbol": sym, "loss": loss_pct,
                              "cost": cost, "price": prices[sym]})
            log.info("  %s  actual=%.1f%%  target=%.1f%%  diff=%+.1f%%  vs cost=%+.1f%%",
                     sym, actual_pct, target_pct, diff, -loss_pct)

        _write_state(account, state_positions, total_value)
        _archive_snapshot()

        if drifts:
            log.warning("Drift threshold breached for %d position(s)", len(drifts))
            notify(_format_drift_report(drifts), title="Rebalance Needed", priority=4, tags="warning")
        else:
            log.info("All positions within %.1f%% tolerance ✓", DRIFT_THRESHOLD_PCT)

        if stops:
            log.warning("Stop-loss threshold (%.0f%%) breached for %d position(s)",
                        STOP_LOSS_PCT, len(stops))
            notify(_format_stop_report(stops), title="Stop-Loss Alert", priority=5, tags="rotating_light")
        else:
            log.info("No position more than %.0f%% below your cost ✓", STOP_LOSS_PCT)

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
