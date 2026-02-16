"""
Reusable risk parity math — uses IB historical data for covariance.

Usage:
    from risk_parity_calc import get_risk_parity_weights
    weights = get_risk_parity_weights(ib, contracts)
    # => {"NVDA": 0.25, "AZN": 0.35, "IGLN": 0.40}
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize


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


def get_risk_parity_weights(ib, contracts: list, duration: str = "2 Y") -> dict[str, float]:
    """
    Fetch historical data from IB, compute covariance, and return
    risk-parity weights as {symbol: weight}.

    Args:
        ib:        Connected IB instance.
        contracts: List of IB Contract objects.
        duration:  How far back to look (IB duration string, e.g. "2 Y").
    """
    closes: dict[str, pd.Series] = {}
    for contract in contracts:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
        )
        if not bars:
            raise ValueError(f"No historical data for {contract.symbol}")
        df = pd.DataFrame(bars)
        closes[contract.symbol] = df.set_index("date")["close"]

    prices = pd.DataFrame(closes).dropna()
    returns = prices.pct_change().dropna()
    cov_matrix = returns.cov()

    tickers = [c.symbol for c in contracts]
    n = len(tickers)
    w0 = np.ones(n) / n
    constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
    bounds = [(0, 1)] * n

    result = minimize(
        _risk_parity_objective, w0, args=(cov_matrix,),
        method="SLSQP", bounds=bounds, constraints=constraints,
    )

    return dict(zip(tickers, result.x))
