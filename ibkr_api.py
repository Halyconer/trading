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

def get_positions(account_id, page_id=0, model=None, sort=None, direction=None, period=None):
    """Retrieves a list of positions for the given account.
    
    Args:
        account_id: String. The account ID.
        page_id: String or int. The page number (0-indexed, max 100 positions per page).
        model: String. Optional. Code for the model portfolio to compare against.
        sort: String. Optional. Column to sort by.
        direction: String. Optional. 'a' for ascending, 'd' for descending.
        period: String. Optional. Period for pnl column (1D, 7D, 1M).
    """
    if not account_id:
        print("ERROR: account_id is required")
        return None
    
    url = f"{BASE_URL}/portfolio/{account_id}/positions/{page_id}"
    print(f"4. Retrieving Positions for {account_id} (Page {page_id}): GET {url}")
    
    # Build query parameters
    params = {}
    if model:
        params['model'] = model
    if sort:
        params['sort'] = sort
    if direction:
        params['direction'] = direction
    if period:
        params['period'] = period
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        positions_data = response.json()
        print("\n--- POSITIONS RESPONSE ---")
        print(json.dumps(positions_data, indent=4))
        print("-------------------------\n")
        print(f"SUCCESS: Positions retrieved for account {account_id}.")
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

def place_market_orders(account_id, orders):
    """Places one or more market orders for the given account.
    
    Args:
        account_id: String. The account ID.
        orders: List of dicts. Each dict should contain:
            - conid: int. Contract ID (required)
            - side: String. "BUY" or "SELL" (required)
            - cashQty: float. Dollar amount to trade (will be converted to shares)
            - tif: String. Time-In-Force. Default "DAY" (optional)
            - orderType: String. Default "MKT" (optional)
            
    Returns:
        Response data from the API
    """

    if not account_id:
        print("ERROR: account_id is required")
        return None
    
    if not orders:
        print("ERROR: orders list is required")
        return None
    
    # Extract conids and get prices for all orders (with fallback to historical)
    conids = [str(order.get("conid")) for order in orders]
    
    # Build a price map: conid -> latest price
    price_map = {}
    print("\n--- Fetching prices for all contracts ---")
    for conid_str in conids:
        conid = int(conid_str)
        price = get_latest_price(conid)
        if price:
            price_map[conid] = price
            print(f"✓ Conid {conid}: Price = ${price}")
        else:
            print(f"✗ Conid {conid}: Price not available")
    
    url = f"{BASE_URL}/iserver/account/{account_id}/orders"
    print(f"\n5. Placing Orders for {account_id}: POST {url}\n")
    
    # Build order objects with quantity calculated from cashQty
    order_list = []
    for order in orders:
        conid = order.get("conid")
        cash_qty = order.get("cashQty")
        
        # Get the price and calculate quantity (rounded down to integer)
        if conid in price_map and cash_qty:
            price = price_map[conid]
            quantity = int(cash_qty / price)  # Round down to integer
            print(f"  Converting ${cash_qty} to {quantity} shares at ${price}/share for conid {conid}")
        else:
            print(f"  ERROR: Could not get price for conid {conid}")
            quantity = 0
        
        order_obj = {
            "acctId": account_id,
            "conid": conid,
            "orderType": order.get("orderType", "MKT"),
            "side": order.get("side", "BUY"),
            "tif": order.get("tif", "DAY"),
            "quantity": quantity,
        }
        order_list.append(order_obj)
    
    request_body = {"orders": order_list}
    
    try:
        response = requests.post(
            url, 
            json=request_body,
            headers=get_headers("POST", request_body),
            verify=False, 
            timeout=10
        )
        response.raise_for_status()
        
        orders_response = response.json()
        print("\n--- PLACE ORDERS RESPONSE ---")
        print(json.dumps(orders_response, indent=4))
        print("-----------------------------\n")
        print(f"SUCCESS: Orders placed for account {account_id}.")
        return orders_response
        
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while placing orders: {e}")
        return None


# --- Main Execution ---
if __name__ == "__main__":
    if check_auth_status():
        ACCOUNT_ID = get_account_ids()
        
        if ACCOUNT_ID:
            #get_account_summary(ACCOUNT_ID)
            
            # Fetch current positions
            get_positions(ACCOUNT_ID, page_id=0, period="1D")
            
            # Place market buy orders: AZN, B, IGLN, NVDA with $1000 each
            orders = [
                {"conid": 4521593, "side": "BUY", "cashQty": 1000},   # AZN
                {"conid": 780709675, "side": "BUY", "cashQty": 1000}, # B
                {"conid": 86656182, "side": "BUY", "cashQty": 1000},  # IGLN
                {"conid": 4815747, "side": "BUY", "cashQty": 1000},   # NVDA
            ]
            place_market_orders(ACCOUNT_ID, orders)
            
    print("Script execution complete.")
