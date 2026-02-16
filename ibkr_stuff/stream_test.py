#!/usr/bin/env python
"""
Stream test — subscribes to live market data and logs prices to a file.

Usage:
    python ibkr_stuff/stream_test.py

Logs to ibkr_stuff/stream.log — tail it in another terminal:
    tail -f ibkr_stuff/stream.log
"""

import logging
from datetime import datetime
from pathlib import Path
from ib_async import IB, util
from config import IB_HOST, IB_PORT, IB_CLIENT_ID

# Log to file + console
log_path = Path(__file__).parent / "stream.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def on_tick(tickers):
    for t in tickers:
        sym = t.contract.symbol
        log.info(f"{sym:6s}  last={t.last}  bid={t.bid}  ask={t.ask}  volume={t.volume}")


def on_error(reqId, errorCode, errorString, contract):
    log.error(f"Error {errorCode}: {errorString}")


def on_disconnect():
    log.warning("Disconnected from IB Gateway")


if __name__ == "__main__":
    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
    ib.reqMarketDataType(3)  # delayed data for paper account

    # Subscribe to live data for all positions
    positions = ib.positions()
    if not positions:
        log.warning("No positions found — nothing to stream")
    else:
        for pos in positions:
            log.info(f"Subscribing to {pos.contract.symbol}")
            ib.reqMktData(pos.contract, '', False, False)

    # Wire up events
    ib.pendingTickersEvent += on_tick
    ib.errorEvent += on_error
    ib.disconnectedEvent += on_disconnect

    log.info(f"Streaming started — logging to {log_path}")
    log.info("Press Ctrl+C to stop")

    try:
        ib.run()
    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        ib.disconnect()
