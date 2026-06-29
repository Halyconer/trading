"""
Reusable risk parity math — uses IB historical data for covariance.

Usage:
    from risk_parity_calc import get_risk_parity_weights
    weights = get_risk_parity_weights(ib, contracts)
    # => {"NVDA": 0.25, "AZN": 0.35, "IGLN": 0.40}

Risk parity sizes each asset to contribute equal risk, so weight is roughly
inverse to volatility. A near-cash asset (e.g. SGOV) has ~zero volatility, so
its risk contribution is ~zero at *any* weight — the optimiser can't equalise
it and its weight comes out essentially undetermined. Such tickers should be
passed in `exclude` and handled as a separate cash sleeve by the caller, not
fed to the optimiser. See the cash-sleeve handling in risk_parity_monitor.py.
"""

import logging

import numpy as np
import pandas as pd
from scipy.optimize import minimize

log = logging.getLogger("rp-calc")


def _portfolio_variance(weights, cov_matrix):
    return np.dot(weights.T, np.dot(cov_matrix, weights))


def _risk_contribution(weights, cov_matrix):
    port_var = _portfolio_variance(weights, cov_matrix)
    marginal = np.dot(cov_matrix, weights)
    return np.multiply(weights, marginal) / port_var


def _risk_parity_objective(weights, cov_matrix):
    rc = _risk_contribution(weights, cov_matrix)
    target = np.mean(rc)
    return np.sum((rc - target) ** 2)


def _fetch_closes(ib, contract, duration: str) -> pd.Series | None:
    """
    Fetch a daily close series for one contract, or None if IB returns nothing.

    Crypto needs different request params than stocks/ETFs: IBKR rejects
    `whatToShow="TRADES"` for crypto (error 321, "Please enter exchange") and
    has no regular-trading-hours concept, so we use AGGTRADES, force the PAXOS
    exchange when the position contract carries none, and drop useRTH.
    """
    is_crypto = contract.secType == "CRYPTO"
    if is_crypto and not contract.exchange:
        contract.exchange = "PAXOS"  # IBKR's crypto venue; required for history
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting="1 day",
        whatToShow="AGGTRADES" if is_crypto else "TRADES",
        useRTH=not is_crypto,
    )
    if not bars:
        return None
    return pd.DataFrame(bars).set_index("date")["close"]


def fetch_price_frame(
    ib, contracts: list, duration: str = "2 Y", exclude: set[str] | None = None
) -> pd.DataFrame:
    """
    Fetch aligned daily closes for `contracts` as a DataFrame (one column per
    symbol), so a single set of IB history requests can feed both the
    risk-parity weights and the stop-loss drawdowns.

    Assets in `exclude` (cash-like, e.g. SGOV) and assets IB returns no history
    for are left out with a log line rather than crashing the run — one bad
    ticker can't take down the daily check.
    """
    exclude = exclude or set()
    closes: dict[str, pd.Series] = {}
    for contract in contracts:
        sym = contract.symbol
        if sym in exclude:
            log.info("  %s — excluded (cash sleeve)", sym)
            continue
        series = _fetch_closes(ib, contract, duration)
        if series is None:
            log.warning("  %s — no historical data, skipping (left to cash sleeve)", sym)
            continue
        closes[sym] = series

    if not closes:
        raise ValueError("No historical data for any risk-parity asset")
    return pd.DataFrame(closes).dropna()


def weights_from_prices(prices: pd.DataFrame) -> dict[str, float]:
    """Risk-parity weights {symbol: weight} (sum to 1) from a price frame."""
    returns = prices.pct_change().dropna()
    cov_matrix = returns.cov()

    tickers = list(prices.columns)
    n = len(tickers)
    w0 = np.ones(n) / n
    constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
    bounds = [(0, 1)] * n

    result = minimize(
        _risk_parity_objective, w0, args=(cov_matrix,),
        method="SLSQP", bounds=bounds, constraints=constraints,
    )
    return dict(zip(tickers, result.x))


def get_risk_parity_weights(
    ib, contracts: list, duration: str = "2 Y", exclude: set[str] | None = None
) -> dict[str, float]:
    """
    Convenience wrapper: fetch history and return risk-parity weights
    {symbol: weight} summing to 1 over the assets actually optimised. A symbol
    missing from the dict means it was excluded or had no data. Prefer
    fetch_price_frame + weights_from_prices when you also need drawdowns.
    """
    prices = fetch_price_frame(ib, contracts, duration, exclude)
    return weights_from_prices(prices)
