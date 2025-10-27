# Finance Portfolio Tools

Risk parity portfolio optimization and IBKR API integration tools.

## Files

- **`risk_parity.py`** — Calculate risk parity weights using historical market data
- **`ibkr_api.py`** — Interactive Brokers Client Portal API wrapper
- **`search_contracts.py`** — Search for contract IDs (conids) by symbol
- **Test files** — Testing utilities for market data and snapshots

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create your local `.env` file from the template:
```bash
cp .env.example .env
```

3. Edit `.env` and add your IBKR account ID:
```env
ACCOUNT_ID=YOUR_ACCOUNT_ID
CONID_AZN=4521593
CONID_B=780709675
CONID_IGLN=86656182
CONID_NVDA=4815747
```

4. Ensure the **IBKR Client Portal Gateway** is running on `https://localhost:5002`

## Usage

### Risk Parity Calculation
```bash
python risk_parity.py
```

Returns optimal portfolio weights that equalize risk contribution across assets.

### Search for Contract IDs
```bash
python search_contracts.py
```

Searches for available contracts by symbol (e.g., AZN, NVDA, IGLN).

### Test Market Data
```bash
python test_snapshot.py
```

Tests connection to IBKR API and retrieves live market snapshots.

## Security Notes

- The IBKR API integration uses `verify=False` for SSL because it connects to a **local gateway** on localhost:5002
- Never commit your account ID to version control
- Use environment variables for sensitive configuration in production

## License

MIT
