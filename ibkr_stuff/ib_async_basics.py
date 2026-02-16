#!/usr/bin/env python
"""
ib_async basics — replaces the Client Portal REST API scripts.
Reads connection settings from .env via config.py.

Usage:
    python ibkr_stuff/ib_async_basics.py [command]

Commands:
    account     Account summary
    positions   Current positions
    market      Live market data snapshot
    historical  Historical bars (30 days, 1 hour)
    all         Run everything (default)
"""

import sys
from ib_async import *
from config import IB_HOST, IB_PORT, IB_CLIENT_ID, TRADING_MODE
from notify import send as notify


def connect():
    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
    ib.reqMarketDataType(3)  # delayed data
    return ib


def show_account(ib):
    print("=" * 60)
    print("ACCOUNT SUMMARY")
    print("=" * 60)
    account = ib.managedAccounts()[0]
    summary = ib.accountSummary(account)
    for item in summary:
        print(f"  {item.tag}: {item.value} {item.currency}")
    print()


def show_positions(ib):
    print("=" * 60)
    print("POSITIONS")
    print("=" * 60)
    positions = ib.positions()
    if not positions:
        print("  No open positions.")
    for pos in positions:
        print(f"  {pos.contract.symbol}: {pos.position} shares "
              f"@ avg cost {pos.avgCost:.2f}")
    print()


def get_position_contracts(ib):
    """Build contract list from actual positions."""
    positions = ib.positions()
    return [pos.contract for pos in positions]


def show_market_data(ib):
    print("=" * 60)
    print("MARKET DATA (snapshot)")
    print("=" * 60)
    contracts = get_position_contracts(ib)
    for contract in contracts:
        ticker = ib.reqMktData(contract, '', True, False)
        ib.sleep(2)
        print(f"  {contract.symbol}: last={ticker.last}  bid={ticker.bid}  ask={ticker.ask}")
        ib.cancelMktData(contract)
    print()


def show_historical(ib):
    print("=" * 60)
    print("HISTORICAL DATA (30 days, 1-hour bars)")
    print("=" * 60)
    contracts = get_position_contracts(ib)
    for contract in contracts:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='30 D',
            barSizeSetting='1 hour',
            whatToShow='TRADES',
            useRTH=True,
        )
        df = util.df(bars)
        if df is not None and not df.empty:
            print(f"\n  {contract.symbol} — {len(df)} bars")
            print(f"  Latest: {df.iloc[-1]['date']}  "
                  f"O={df.iloc[-1]['open']:.2f}  H={df.iloc[-1]['high']:.2f}  "
                  f"L={df.iloc[-1]['low']:.2f}  C={df.iloc[-1]['close']:.2f}")
        else:
            print(f"\n  {contract.symbol} — no data returned")
    print()


COMMANDS = {
    'account': show_account,
    'positions': show_positions,
    'market': show_market_data,
    'historical': show_historical,
}


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'

    print(f"Mode: {TRADING_MODE} | Port: {IB_PORT}")
    ib = connect()
    account = ib.managedAccounts()[0]
    print(f"Connected to IB Gateway (account: {account})\n")
    notify(f"Connected to {account} ({TRADING_MODE})", title="IB Gateway")

    try:
        if cmd == 'all':
            for fn in COMMANDS.values():
                fn(ib)
        elif cmd in COMMANDS:
            COMMANDS[cmd](ib)
        else:
            print(f"Unknown command: {cmd}")
            print(f"Available: {', '.join(COMMANDS)} or all")
    finally:
        ib.disconnect()
        print("Disconnected.")
