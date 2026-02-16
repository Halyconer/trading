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
