import pandas as pd
import yfinance as yf
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import numpy as np

tickers = ['SPY', 'TLT', 'GLD']  
data = yf.download(tickers, start="2015-01-01", end="2024-01-01", progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data = data['Close']
returns = data.pct_change().dropna()

def calculate_portfolio_variance(weights, cov_matrix):
    return np.dot(weights.T, np.dot(cov_matrix, weights))

def calculate_risk_contribution(weights, cov_matrix):
    portfolio_variance = calculate_portfolio_variance(weights, cov_matrix)
    marginal_contrib = np.dot(cov_matrix, weights)
    risk_contrib = np.multiply(weights, marginal_contrib) / portfolio_variance
    return risk_contrib

def risk_parity_objective(weights, cov_matrix):
    risk_contrib = calculate_risk_contribution(weights, cov_matrix)
    target_risk = np.mean(risk_contrib)
    return np.sum((risk_contrib - target_risk) ** 2)

def get_risk_parity_weights(cov_matrix):
    num_assets = len(cov_matrix)
    initial_weights = np.ones(num_assets) / num_assets
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = [(0, 1) for _ in range(num_assets)]
    
    result = minimize(risk_parity_objective, initial_weights, args=(cov_matrix,), 
                      method='SLSQP', bounds=bounds, constraints=constraints)
    
    return result.x

cov_matrix = returns.cov()
risk_parity_weights = get_risk_parity_weights(cov_matrix)
print("Risk Parity Weights:", risk_parity_weights)