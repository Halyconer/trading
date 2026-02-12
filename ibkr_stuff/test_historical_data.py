#!/usr/bin/env python
"""Test script to verify get_latest_price function with historical data fallback"""

import requests
import json
import urllib3
from ibkr_api import check_auth_status, get_latest_price, get_headers

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if __name__ == "__main__":
    print("=" * 70)
    print("Testing get_latest_price() with Historical Data Fallback")
    print("=" * 70)
    
    # Step 1: Check authentication
    if not check_auth_status():
        print("ERROR: Not authenticated. Cannot proceed.")
        exit(1)
    
    # Step 2: Pre-flight request
    print("\nMaking pre-flight request to /iserver/accounts...")
    try:
        url = "https://localhost:5002/v1/api/iserver/accounts"
        response = requests.get(url, headers=get_headers("GET"), verify=False, timeout=10)
        response.raise_for_status()
        print("✓ Pre-flight request successful\n")
    except requests.exceptions.RequestException as e:
        print(f"✗ Pre-flight request failed: {e}\n")
    
    # Step 3: Test with real conids
    test_conids = [
        (851181134, "AZN"),
        (780709675, "B"),
        (86656182, "IGLN"),
        (4815747, "NVDA")
    ]
    
    print("=" * 70)
    print("Fetching latest prices (with historical data fallback):")
    print("=" * 70 + "\n")
    
    for conid, symbol in test_conids:
        print(f"Getting price for {symbol} (conid: {conid})...")
        price = get_latest_price(conid)
        if price:
            print(f"✓ {symbol}: ${price}\n")
        else:
            print(f"✗ {symbol}: Price not available\n")
    
    print("=" * 70)
    print("Test complete!")
    print("=" * 70)
