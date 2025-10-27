import pandas as pd
import yfinance as yf
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import numpy as np
import os
from dotenv import load_dotenv
from ibkr_api import check_auth_status, get_positions

# Load environment variables
load_dotenv()

# Get account ID
account_id = os.getenv("ACCOUNT_ID")

print("=" * 60)
print("RISK PARITY PORTFOLIO CALCULATOR")
print("=" * 60 + "\n")

# Check authentication
print("Checking IBKR authentication...")
if not check_auth_status():
    print("ERROR: Not authenticated to IBKR Gateway.")
    exit(1)

# Get current positions
print(f"\nFetching positions for account {account_id}...")
positions = get_positions(account_id)

if not positions:
    print("ERROR: No positions found in portfolio.")
    exit(1)

# Extract tickers from positions
tickers = [pos.get("description", pos.get("ticker", "")) for pos in positions if pos.get("position", 0) != 0]

if not tickers:
    print("ERROR: No valid tickers found in positions.")
    exit(1)

print(f"\nPortfolio Tickers: {', '.join(tickers)}")
print(f"Downloading historical data...\n")

# Download historical data
data = yf.download(tickers, start="2015-01-01", end="2024-01-01", progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data = data['Close']

returns = data.pct_change().dropna()

def calculate_portfolio_variance(weights, cov_matrix):
    """Calculate portfolio variance."""
    return np.dot(weights.T, np.dot(cov_matrix, weights))

def calculate_risk_contribution(weights, cov_matrix):
    """Calculate risk contribution of each asset."""
    portfolio_variance = calculate_portfolio_variance(weights, cov_matrix)
    marginal_contrib = np.dot(cov_matrix, weights)
    risk_contrib = np.multiply(weights, marginal_contrib) / portfolio_variance
    return risk_contrib

def risk_parity_objective(weights, cov_matrix):
    """Objective function: minimize squared deviations from equal risk contribution."""
    risk_contrib = calculate_risk_contribution(weights, cov_matrix)
    target_risk = np.mean(risk_contrib)
    return np.sum((risk_contrib - target_risk) ** 2)

def get_risk_parity_weights(cov_matrix, num_assets):
    """Optimize for risk parity weights using SLSQP."""
    initial_weights = np.ones(num_assets) / num_assets
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = [(0, 1) for _ in range(num_assets)]
    
    result = minimize(risk_parity_objective, initial_weights, args=(cov_matrix,), 
                      method='SLSQP', bounds=bounds, constraints=constraints)
    
    return result.x

# Calculate covariance matrix
cov_matrix = returns.cov()

# Get risk parity weights
risk_parity_weights = get_risk_parity_weights(cov_matrix, len(tickers))

# Display results
print("\n" + "=" * 60)
print("RISK PARITY PORTFOLIO ALLOCATION")
print("=" * 60)
for ticker, weight in zip(tickers, risk_parity_weights):
    print(f"{ticker:8} {weight*100:6.2f}%")
print("=" * 60)
print(f"Total:   {sum(risk_parity_weights)*100:6.2f}%")
print()

# Calculate and display risk contributions
risk_contrib = calculate_risk_contribution(risk_parity_weights, cov_matrix)
print("Risk Contributions:")
for ticker, contrib in zip(tickers, risk_contrib):
    print(f"{ticker:8} {contrib*100:6.2f}%")
print()

# Save to CSV
output_df = pd.DataFrame({
    'Ticker': tickers,
    'Risk_Parity_Weight_%': risk_parity_weights * 100,
    'Risk_Contribution_%': risk_contrib * 100
})

output_file = 'risk_parity_output.csv'
output_df.to_csv(output_file, index=False)
print(f"✓ Results saved to {output_file}")

