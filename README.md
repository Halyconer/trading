# Finance

Personal portfolio tooling on top of Interactive Brokers via [`ib_async`](https://github.com/erdewit/ib_async).

The live risk-parity monitor is the foundation: it holds an IB Gateway session, streams prices for current positions, and writes a `state.json` snapshot that downstream consumers (alerts, news ingest, public portfolio site) can read without opening their own IB session.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy the env template and fill it in:
   ```bash
   cp .env.example .env
   ```

3. Start **IB Gateway** (paper on port 4002, live on 4001) and log in.

## Run the monitor

```bash
python ibkr_stuff/risk_parity_monitor.py
```

Connects to IB Gateway, subscribes to streaming market data for every open position, computes risk-parity target weights once at startup, then re-checks drift every `CHECK_INTERVAL_SECS`. Sends an ntfy.sh push notification when any position drifts beyond `DRIFT_THRESHOLD_PCT`. After each check it writes `state.json` at the repo root.

## Other scripts in `ibkr_stuff/`

- `mirror_positions.py` — replicate a hard-coded position list into the paper account (dry-run by default; `--execute` to place orders).
- `place_orders.py` / `order_tracker.py` — order placement and status helpers.
- `search_contracts.py` — look up IB contract IDs by symbol.
- `risk_parity_calc.py` — covariance + SLSQP risk-parity weight solver, fed by IB historical data.
- `notify.py` — thin ntfy.sh wrapper.
- `config.py` — env-driven config shared by all of the above.
