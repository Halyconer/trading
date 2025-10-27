import requests
import json
import urllib3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress warnings about insecure request (since we are using verify=False)
# The IBKR Client Portal Gateway uses a self-signed certificate on localhost:5002
# which requires disabling SSL verification in the client. This is normal and safe
# because the request is between your machine and the local gateway.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_headers(method="GET", data=None):
    """Build request headers with proper Content-Length for POST requests."""
    headers = {
        "Host": "api.ibkr.com",
        "User-Agent": "Python-Client/1.0",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    
    # Add Content-Length for POST requests
    if method == "POST":
        content = json.dumps(data) if data else ""
        headers["Content-Length"] = str(len(content.encode('utf-8')))
    
    return headers

# --- Configuration ---
HOST = os.getenv("IBKR_HOST", "https://localhost:5002")
BASE_URL = f"{HOST}/v1/api"
ACCOUNT_ID = os.getenv("ACCOUNT_ID") 

# --- API Functions ---
def check_auth_status():
    """Checks the current authentication and connection status."""
    url = f"{BASE_URL}/iserver/auth/status"
    print(f"1. Checking Authentication Status: GET {url}")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), verify=False, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        status_data = response.json()
        print("\n--- AUTH STATUS RESPONSE ---")
        print(json.dumps(status_data, indent=4))
        print("----------------------------\n")
        
        if status_data.get("authenticated") and status_data.get("connected"):
            print("SUCCESS: Authenticated and Connected to IBKR Gateway.")
            return True
        else:
            print("ERROR: Not authenticated. Please log into the Gateway via your browser at:", HOST)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while checking authentication: {e}")
        return False

def get_account_ids():
    """Retrieves a list of all accessible account IDs."""
    url = f"{BASE_URL}/portfolio/accounts"
    print(f"2. Retrieving Account IDs: GET {url}")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), verify=False, timeout=10)
        response.raise_for_status()
        
        accounts_data = response.json()
        print("\n--- ACCOUNT IDS RESPONSE ---")
        print(json.dumps(accounts_data, indent=4))
        print("----------------------------\n")
        
        if accounts_data and isinstance(accounts_data, list):
            first_account_id = accounts_data[0].get("accountId")
            print(f"SUCCESS: Found {len(accounts_data)} account(s). First ID: {first_account_id}")
            return first_account_id
        else:
            print("WARNING: Response received but no account data was found.")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while getting account IDs: {e}")
        return None

def get_account_summary(account_id):
    """Retrieves a detailed summary for a specific account."""
    if not account_id:
        return
        
    url = f"{BASE_URL}/portfolio/{account_id}/summary"
    print(f"3. Retrieving Account Summary for {account_id}: GET {url}")

    try:
        response = requests.get(url, headers=get_headers("GET"), verify=False, timeout=10)
        response.raise_for_status()

        summary_data = response.json()
        print("\n--- ACCOUNT SUMMARY RESPONSE ---")
        print(f"Total Cash Value: {summary_data.get('totalCashValue', {}).get('value')}")
        print(f"Net Liquidation Value: {summary_data.get('netLiquidationValue', {}).get('value')}")
        print(json.dumps(summary_data, indent=4))
        print("--------------------------------\n")
        print(f"SUCCESS: Detailed summary retrieved for account {account_id}.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while getting the account summary: {e}")

def get_position_by_conid(account_id, conid):
    """Retrieves detailed position information for a specific contract.
    
    Args:
        account_id: String. The account ID.
        conid: String or int. The contract ID to get position for.
    
    Returns:
        Position data with details like position size, market price, P&L, etc.
    """
    if not account_id or not conid:
        print("ERROR: account_id and conid are required")
        return None
    
    url = f"{BASE_URL}/portfolio/{account_id}/position/{conid}"
    print(f"Getting position for conid {conid}: GET {url}")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), verify=False, timeout=10)
        response.raise_for_status()
        
        position_data = response.json()
        
        # Display key position information
        if position_data:
            print(f"\n--- POSITION DATA FOR CONID {conid} ---")
            
            # Key fields to display
            ticker = position_data.get("ticker", "N/A")
            position = position_data.get("position", 0)
            mkt_price = position_data.get("mktPrice", 0)
            mkt_value = position_data.get("mktValue", 0)
            avg_price = position_data.get("avgPrice", 0)
            unrealized_pnl = position_data.get("unrealizedPnl", 0)
            realized_pnl = position_data.get("realizedPnl", 0)
            currency = position_data.get("currency", "USD")
            
            print(f"Ticker: {ticker}")
            print(f"Position: {position} shares")
            print(f"Market Price: ${mkt_price} {currency}")
            print(f"Market Value: ${mkt_value}")
            print(f"Avg Cost: ${avg_price}/share")
            print(f"Unrealized P&L: ${unrealized_pnl}")
            print(f"Realized P&L: ${realized_pnl}")
            print(f"-----------------------------------\n")
            
            return position_data
        else:
            print("No position data found")
            return None
        
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while getting position: {e}")
        return None

def get_positions(account_id, conids=None, model=None, sort=None, direction=None):
    """Retrieves near real-time positions for the given account.
    
    Uses the newer /portfolio2 endpoint which provides near-real-time updates
    and removes caching found in the older endpoint.
    
    Args:
        account_id: String. The account ID.
        conids: List of contract IDs to filter (optional).
        model: String. Optional. Code for the model portfolio to compare against.
        sort: String. Optional. Column to sort by.
        direction: String. Optional. 'a' for ascending, 'd' for descending.
    
    Returns:
        List of position data
    """
    if not account_id:
        print("ERROR: account_id is required")
        return None
    
    # Use the newer portfolio2 endpoint for real-time data
    url = f"{BASE_URL}/portfolio2/{account_id}/positions"
    print(f"Retrieving positions for {account_id}: GET {url}")
    
    # Build query parameters
    params = {}
    if model:
        params['model'] = model
    if sort:
        params['sort'] = sort
    if direction:
        params['direction'] = direction
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        positions_data = response.json()
        
        # Filter by conids if provided
        if conids:
            if not isinstance(conids, list):
                conids = [conids]
            positions_data = [p for p in positions_data if p.get("conid") in conids]
        
        print("\n--- POSITIONS RESPONSE ---")
        print(json.dumps(positions_data, indent=4))
        print("-------------------------\n")
        
        # Display summary
        if positions_data:
            print("Position Summary:")
            for pos in positions_data:
                desc = pos.get("description", "Unknown")
                position = pos.get("position", 0)
                mkt_price = pos.get("marketPrice", 0)
                mkt_value = pos.get("marketValue", 0)
                unrealized_pnl = pos.get("unrealizedPnl", 0)
                currency = pos.get("currency", "USD")
                
                print(f"  {desc}: {position} shares @ ${mkt_price} = ${mkt_value} {currency} (P&L: ${unrealized_pnl})")
        
        print(f"\nSUCCESS: {len(positions_data)} position(s) retrieved for account {account_id}.")
        return positions_data
        
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while getting positions: {e}")
        return None

def get_market_data(conids, fields="31"):
    """Gets live market data snapshot for one or more contracts.
    
    Args:
        conids: String or list. Contract ID(s). Can be comma-separated string or list.
        fields: String. Comma-separated field IDs. Default "31" is last price.
                Common fields: 31=Last Price, 84=Bid, 86=Ask
    
    Returns:
        List of market data snapshots with price information
    """
    
    # Convert list to comma-separated string if needed
    if isinstance(conids, list):
        conids = ",".join(map(str, conids))
    
    url = f"{BASE_URL}/iserver/marketdata/snapshot"
    params = {
        "conids": conids,
        "fields": fields
    }
    
    print(f"Getting Market Data for conids: {conids}")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        market_data = response.json()
        print("\n--- MARKET DATA RESPONSE ---")
        print(json.dumps(market_data, indent=4))
        print("---------------------------\n")
        
        return market_data
        
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while getting market data: {e}")
        return None

def get_historical_data(conid, period="1d", bar="1d"):
    """Gets historical market data for a contract.
    
    Args:
        conid: String or int. Contract ID.
        period: String. Duration (default "1d"). Format: {1-30}min, {1-8}h, {1-1000}d, {1-792}w, {1-182}m, {1-15}y
        bar: String. Bar size (default "1d"). Format: 1min, 5min, 1h, 1d, 1w, 1m
    
    Returns:
        Tuple of (historical_data, close_price)
    """
    
    url = f"{BASE_URL}/iserver/marketdata/history"
    params = {
        "conid": conid,
        "period": period,
        "bar": bar,
        "outsideRth": "true"
    }
    
    print(f"Getting historical data for conid {conid} (period: {period}, bar: {bar})")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        hist_data = response.json()
        
        # Extract the most recent close price
        if hist_data and isinstance(hist_data, dict):
            bars = hist_data.get("data", [])
            if bars:
                # Last entry is the most recent
                latest_bar = bars[-1]
                close_price = latest_bar.get("c")  # 'c' is close price
                if close_price:
                    print(f"  ✓ Latest Close Price: ${close_price}")
                    return hist_data, close_price
        
        return hist_data, None
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 500:
            print(f"  ✗ 500 Error - Contract may not support historical data or conid incorrect")
        else:
            print(f"  ✗ HTTP Error {e.response.status_code}: {e}")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request error: {e}")
        return None, None

def get_latest_price(conid):
    """Get the latest price for a contract, trying snapshot first, then historical data.
    
    Args:
        conid: String or int. Contract ID.
    
    Returns:
        Latest price (float) or None if not available
    """
    
    # Try market data snapshot first
    market_data = get_market_data([conid], fields="31")
    
    if market_data and isinstance(market_data, list) and len(market_data) > 0:
        price = market_data[0].get("31")
        if price:
            return float(price)
    
    # Fallback to historical data if snapshot returns None
    print("  (Market data snapshot unavailable, trying historical data...)")
    
    # Try multiple period/bar combinations for robustness
    attempts = [
        ("1d", "1d"),
        ("5d", "1d"),
        ("1w", "1d"),
    ]
    
    for period, bar in attempts:
        _, price = get_historical_data(conid, period=period, bar=bar)
        if price:
            return float(price)
    
    return None

def place_market_order(account_id: str, conid: int, side: str = "BUY", cash_qty: float = None, 
                       quantity: int = None, order_type: str = "MKT", tif: str = "DAY"):
    """Places a single market order for the given account.
    
    Args:
        account_id: String. The account ID.
        conid: int. Contract ID (required)
        side: String. "BUY" or "SELL" (default "BUY")
        cash_qty: float. Dollar amount to trade (will be converted to shares). 
                 Either cash_qty or quantity must be provided.
        quantity: int. Number of shares to trade. 
                 Either cash_qty or quantity must be provided.
        order_type: String. Order type (default "MKT")
        tif: String. Time-In-Force (default "DAY")
            
    Returns:
        Response data from the API, or None if error
    """

    if not account_id:
        print("ERROR: account_id is required")
        return None
    
    if not conid:
        print("ERROR: conid is required")
        return None
    
    # Determine quantity
    if quantity is None:
        if cash_qty is None:
            print("ERROR: Either quantity or cash_qty must be provided")
            return None
        
        # Get price and convert cashQty to shares
        price = get_latest_price(conid)
        if not price:
            print(f"ERROR: Could not get price for conid {conid}")
            return None
        
        quantity = int(cash_qty / price)
        print(f"Converting ${cash_qty} to {quantity} shares at ${price}/share for conid {conid}")
    
    url = f"{BASE_URL}/iserver/account/{account_id}/orders"
    
    # Build single order object according to IBKR API spec
    order_obj = {
        "acctId": account_id,
        "conid": conid,
        "orderType": order_type,
        "side": side,
        "tif": tif,
        "quantity": quantity,
    }
    
    # Wrap in orders array as required by IBKR API
    request_body = {"orders": [order_obj]}
    
    try:
        response = requests.post(
            url, 
            json=request_body,
            headers=get_headers("POST", request_body),
            verify=False, 
            timeout=10
        )
        response.raise_for_status()
        
        order_response = response.json()
        print(f"\n--- PLACE ORDER RESPONSE ---")
        print(json.dumps(order_response, indent=4))
        print("---------------------------\n")
        print(f"SUCCESS: Order submitted for conid {conid} ({quantity} shares {side})")
        return order_response
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: An error occurred while placing order for conid {conid}: {e}")
        return None


def confirm_order_reply(reply_id, confirmed=True):
    """Confirms an order reply (e.g., market data warning).
    
    Args:
        reply_id: String. The reply ID from the order response.
        confirmed: Boolean. True to confirm, False to cancel.
    
    Returns:
        Response data from the API, or None if error
    """
    url = f"{BASE_URL}/iserver/reply/{reply_id}"
    
    request_body = {"confirmed": confirmed}
    
    print(f"\nConfirming order reply {reply_id}...")
    
    try:
        response = requests.post(
            url,
            json=request_body,
            headers=get_headers("POST", request_body),
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        
        reply_response = response.json()
        print(f"--- REPLY CONFIRMATION RESPONSE ---")
        print(json.dumps(reply_response, indent=4))
        print("----------------------------------\n")
        
        return reply_response
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: An error occurred while confirming reply: {e}")
        return None

def get_live_orders(filters=None, force=False):
    """Retrieves live orders for the account.
    
    Args:
        filters: String. Filter by status ("submitted", "filled", "cancelled", comma-separated).
        force: Boolean. Force a fresh request and clear cached behavior.
    
    Returns:
        List of orders
    """
    url = f"{BASE_URL}/iserver/account/orders"
    params = {}
    
    if filters:
        params["filters"] = filters
    if force:
        params["force"] = "true"
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        orders = data.get("orders", []) if isinstance(data, dict) else []
        
        print(f"\nFound {len(orders)} order(s)")
        return orders
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
        return []

def get_order_status(order_id):
    """Gets detailed status of a specific order.
    
    Args:
        order_id: String. The order ID to check.
    
    Returns:
        Order status data
    """
    url = f"{BASE_URL}/iserver/account/order/{order_id}"
    
    print(f"Getting order status for {order_id}: GET {url}")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), verify=False, timeout=10)
        response.raise_for_status()
        
        order_data = response.json()
        
        print("\n--- ORDER STATUS RESPONSE ---")
        print(json.dumps(order_data, indent=4))
        print("----------------------------\n")
        
        if order_data:
            status = order_data.get("status", "N/A")
            qty = order_data.get("quantity", 0)
            filled = order_data.get("filledQuantity", 0)
            remaining = qty - filled
            
            print(f"Order {order_id} Status: {status}")
            print(f"  Quantity: {qty}")
            print(f"  Filled: {filled}")
            print(f"  Remaining: {remaining}")
        
        return order_data
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: An error occurred while getting order status: {e}")
        return None
