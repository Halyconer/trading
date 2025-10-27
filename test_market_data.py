import requests
import json
import urllib3
from ibkr_api import check_auth_status, get_account_ids, get_market_data, get_headers

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if __name__ == "__main__":
    print("=" * 60)
    print("Testing get_market_data() Function")
    print("=" * 60)
    
    # Step 1: Check authentication
    if not check_auth_status():
        print("ERROR: Not authenticated. Cannot proceed.")
        exit(1)
    
    # Step 1.5: Pre-flight request - must call /iserver/accounts before market data
    print("\nMaking pre-flight request to /iserver/accounts...")
    try:
        url = "https://localhost:5002/v1/api/iserver/accounts"
        response = requests.get(url, headers=get_headers("GET"), verify=False, timeout=10)
        response.raise_for_status()
        print("✓ Pre-flight request successful\n")
    except requests.exceptions.RequestException as e:
        print(f"✗ Pre-flight request failed: {e}\n")
    
    # Step 2: Test with sample contract IDs
    # Using the real conids from search_contracts.py
    test_conids = [4521593, 780709675, 86656182, 4815747]
    
    print("Testing market data retrieval for:")
    print(f"  - AZN (conid: 4521593)")
    print(f"  - B (conid: 780709675)")
    print(f"  - IGLN (conid: 86656182)")
    print(f"  - NVDA (conid: 4815747)")
    print("\n" + "-" * 60)
    
    # Call get_market_data
    market_data = get_market_data(test_conids, fields="31")
    
    if market_data:
        print("\n" + "=" * 60)
        print("SUCCESS: get_market_data() returned data")
        print("=" * 60)
        
        # Parse and display the results
        if isinstance(market_data, list):
            for item in market_data:
                conid = item.get("conid")
                price = item.get("31")
                print(f"\nConid {conid}: Last Price = {price}")
    else:
        print("\n" + "=" * 60)
        print("ERROR: get_market_data() failed or returned None")
        print("=" * 60)
