#!/usr/bin/env python
"""Search for contract conids by symbol"""

import requests
import json
import urllib3
from ibkr_api import check_auth_status, get_headers

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuration ---
HOST = "https://localhost:5002"
BASE_URL = f"{HOST}/v1/api"

def search_contract_by_symbol(symbol):
    """Search for a contract by symbol using /iserver/secdef/search.
    
    Args:
        symbol: String. The ticker symbol (e.g., "AZN", "NVDA")
    
    Returns:
        List of matching contracts with conid, symbol, secType, etc.
    """
    
    url = f"{BASE_URL}/iserver/secdef/search"
    params = {
        "symbol": symbol,
        "secType": "STK"  # Search for stocks only
    }
    
    print(f"\nSearching for {symbol}...")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        results = response.json()
        
        if results and isinstance(results, list):
            print(f"✓ Found {len(results)} result(s) for {symbol}\n")
            print(f"--- Full Response for {symbol} ---")
            print(json.dumps(results, indent=2))
            print("---" + "-" * (len(symbol) + 18) + "\n")
            
            # Display each result with key details
            for idx, contract in enumerate(results, 1):
                conid = contract.get("conid")
                name = contract.get("name")
                desc = contract.get("description")
                sym = contract.get("symbol")
                sectype = contract.get("secType")
                listingExch = contract.get("listingExchange")
                
                print(f"Option {idx}:")
                print(f"  Conid: {conid}")
                print(f"  Symbol: {sym}")
                print(f"  Name: {name}")
                print(f"  Type: {sectype}")
                print(f"  Listing Exchange: {listingExch}")
                print(f"  Description: {desc}\n")
            
            # Return all results so user can choose
            return results
        else:
            print(f"✗ No results found for {symbol}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"An error occurred searching for {symbol}: {e}")
        return None

def search_multiple_contracts(symbols):
    """Search for multiple contracts and display all results.
    
    Args:
        symbols: List of ticker symbols
    
    Returns:
        Dictionary mapping symbol -> list of all matching results
    """
    
    all_results = {}
    
    for symbol in symbols:
        results = search_contract_by_symbol(symbol)
        if results:
            all_results[symbol] = results
        else:
            all_results[symbol] = None
    
    return all_results

# --- Main Execution ---
if __name__ == "__main__":
    print("=" * 70)
    print("Contract Conid Lookup Tool - Show All Results")
    print("=" * 70 + "\n")
    
    # Check authentication first
    if not check_auth_status():
        print("ERROR: Not authenticated. Cannot proceed.")
        exit(1)
    
    print("\n" + "=" * 70)
    print("Searching for contracts by symbol...")
    print("=" * 70)
    
    # Search for contracts by symbol
    symbols = ["AZN", "B", "IGLN", "NVDA"]
    all_results = search_multiple_contracts(symbols)
    
    print("\n" + "=" * 70)
    print("SUMMARY - Select the correct conid for each symbol:")
    print("=" * 70)
    
    # Create a summary table
    selected_conids = {}
    for symbol in symbols:
        results = all_results.get(symbol)
        if results:
            print(f"\n{symbol}:")
            print("-" * 70)
            for idx, contract in enumerate(results, 1):
                conid = contract.get("conid")
                name = contract.get("name")
                listingExch = contract.get("listingExchange")
                print(f"  [{idx}] Conid: {conid} | Exchange: {listingExch} | {name}")
            
            # Use the first result by default
            selected_conids[symbol] = results[0].get("conid")
        else:
            print(f"\n{symbol}: NOT FOUND")
            selected_conids[symbol] = None
    
    print("\n" + "=" * 70)
    print("RECOMMENDED conids (using first/primary listing):")
    print("=" * 70)
    for symbol, conid in selected_conids.items():
        if conid:
            print(f"{symbol}: {conid}")
        else:
            print(f"{symbol}: NOT FOUND")
    
    print("\n" + "=" * 70)
    print("Copy this into ibkr_api.py:")
    print("=" * 70)
    print("""
    orders = [
        {"conid": """ + str(selected_conids.get("AZN", "???")) + """, "side": "BUY", "cashQty": 1000},  # AZN
        {"conid": """ + str(selected_conids.get("B", "???")) + """, "side": "BUY", "cashQty": 1000},    # B (Barrick Mining)
        {"conid": """ + str(selected_conids.get("IGLN", "???")) + """, "side": "BUY", "cashQty": 1000},    # IGLN
        {"conid": """ + str(selected_conids.get("NVDA", "???")) + """, "side": "BUY", "cashQty": 1000},    # NVDA
    ]
    """)
