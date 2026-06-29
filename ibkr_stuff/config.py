"""
Centralised config for ib_async scripts.
Reads from .env so each machine (Mac, Pi) can have its own settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Trading mode
TRADING_MODE = os.getenv("IB_TRADING_MODE", "paper").lower()

# Connection
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "1"))

# Port: explicit env var wins, otherwise derive from mode
_default_port = 4002 if TRADING_MODE == "paper" else 4001
IB_PORT = int(os.getenv("IB_PORT", str(_default_port)))

# Notifications
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
NTFY_ENABLED = os.getenv("NTFY_ENABLED", "off").lower() == "on"

# Risk parity monitor
DRIFT_THRESHOLD_PCT = float(os.getenv("DRIFT_THRESHOLD_PCT", "5.0"))
CHECK_INTERVAL_SECS = int(os.getenv("CHECK_INTERVAL_SECS", "3600"))

# Cash-like tickers held as a separate sleeve, kept OUT of the risk-parity
# optimisation (a near-zero-volatility asset breaks equal-risk sizing — see
# risk_parity_calc.py). These are pinned to their current weight, so they never
# generate a bogus drift alert. Comma-separated, e.g. "SGOV,BIL".
CASH_TICKERS = {t.strip().upper() for t in os.getenv("CASH_TICKERS", "SGOV").split(",") if t.strip()}

# Stop-loss recommender: flag a position now down this many percent from YOUR
# average cost (the lot you bought), as an *alert* — it never places an order.
# 0 disables. Applied only to the risky sleeve (cash like SGOV is exempt).
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "15.0"))
