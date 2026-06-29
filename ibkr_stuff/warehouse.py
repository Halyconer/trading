#!/usr/bin/env python
"""
DuckDB research warehouse — the persistent, queryable history the flat files
don't keep.

`state.json` is overwritten every run, so it only ever holds "now". This module
*appends* each snapshot into a DuckDB database (one file, no server) so a real
time-series builds up over time — the foundation the backtester (see
`legion-node.md`) will later read.

DuckDB is an embedded, relational, columnar database — plain SQL, but stored
column-at-a-time so the "scan years of rows and aggregate" queries backtests do
are fast. The whole DB is a single file, so it's trivial to copy to the Legion
when that node comes online.

Usage:
    # append the current state.json into the warehouse (idempotent)
    python ibkr_stuff/warehouse.py ingest

    # show what's stored (row counts, latest snapshot)
    python ibkr_stuff/warehouse.py summary
"""

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "state.json"
DB_PATH = REPO_ROOT / "data" / "market.duckdb"

# Per-position columns we carry from state.json, in table order.
POSITION_COLS = [
    "symbol", "quantity", "price", "avg_cost", "market_value",
    "weight_actual_pct", "weight_target_pct", "drift_pct", "loss_vs_cost_pct",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS position_snapshots (
    captured_at        TIMESTAMPTZ,   -- when the snapshot was taken (UTC)
    account            VARCHAR,
    trading_mode       VARCHAR,
    total_value        DOUBLE,        -- whole-portfolio value at that moment
    symbol             VARCHAR,
    quantity           DOUBLE,
    price              DOUBLE,
    avg_cost           DOUBLE,        -- your lot / entry price (per share/coin)
    market_value       DOUBLE,
    weight_actual_pct  DOUBLE,
    weight_target_pct  DOUBLE,        -- risk-parity target (cash sleeve pinned)
    drift_pct          DOUBLE,
    loss_vs_cost_pct   DOUBLE,        -- + = underwater vs cost
    -- one row per symbol per snapshot; re-ingesting the same file is a no-op
    PRIMARY KEY (captured_at, symbol)
);
"""


def connect() -> duckdb.DuckDBPyConnection:
    """Open (creating if needed) the warehouse and ensure the schema exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA)
    return con


def ingest_state(con: duckdb.DuckDBPyConnection, state_path: Path = STATE_PATH) -> int:
    """
    Append one state.json snapshot into position_snapshots. Idempotent: the
    (captured_at, symbol) primary key + INSERT OR IGNORE means re-running on the
    same file inserts nothing. Returns the number of rows actually added.
    """
    if not state_path.exists():
        raise FileNotFoundError(f"No state file at {state_path} — run the monitor first.")

    state = json.loads(state_path.read_text())

    # Flatten: a per-position frame, with the snapshot-level fields broadcast
    # onto every row. reindex() tolerates older snapshots missing a column.
    df = pd.DataFrame(state["positions"]).reindex(columns=POSITION_COLS)
    df.insert(0, "captured_at", pd.to_datetime(state["updated_at"], utc=True))
    df.insert(1, "account", state["account"])
    df.insert(2, "trading_mode", state["trading_mode"])
    df.insert(3, "total_value", state["total_value"])

    before = con.execute("SELECT count(*) FROM position_snapshots").fetchone()[0]
    # DuckDB reads the local pandas frame directly — no load step.
    con.register("incoming", df)
    con.execute("INSERT OR IGNORE INTO position_snapshots SELECT * FROM incoming")
    con.unregister("incoming")
    after = con.execute("SELECT count(*) FROM position_snapshots").fetchone()[0]
    return after - before


def summary(con: duckdb.DuckDBPyConnection) -> None:
    """Print row counts and the most recent snapshot — a quick health check."""
    rows, snaps, syms = con.execute("""
        SELECT count(*), count(DISTINCT captured_at), count(DISTINCT symbol)
        FROM position_snapshots
    """).fetchone()
    print(f"position_snapshots: {rows} rows across {snaps} snapshot(s), {syms} symbol(s)")
    if rows == 0:
        return

    latest = con.execute("SELECT max(captured_at) FROM position_snapshots").fetchone()[0]
    print(f"\nLatest snapshot — {latest}:")
    print(con.execute("""
        SELECT symbol, market_value, weight_actual_pct, drift_pct, loss_vs_cost_pct
        FROM position_snapshots
        WHERE captured_at = (SELECT max(captured_at) FROM position_snapshots)
        ORDER BY market_value DESC
    """).fetchdf().to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="DuckDB research warehouse.")
    parser.add_argument("command", choices=["ingest", "summary"],
                        help="ingest = append state.json; summary = show contents")
    args = parser.parse_args()

    con = connect()
    try:
        if args.command == "ingest":
            added = ingest_state(con)
            print(f"Ingested state.json → {added} new row(s).")
            summary(con)
        elif args.command == "summary":
            summary(con)
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
