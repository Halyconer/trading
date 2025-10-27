#!/usr/bin/env python
"""Test Top-of-Book Snapshots with pre-flight request"""

import requests
import json
import urllib3
from ibkr_api import check_auth_status, get_headers

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
HOST = "https://localhost:5002"
BASE_URL = f"{HOST}/v1/api"

def preflight_snapshot(conids, fields):
    """Make pre-flight request to start streaming market data.
    
    This request initializes the data stream for the specified contracts.
    The first request won't return data, just confirms streaming started.
    
    Args:
        conids: List of contract IDs or comma-separated string
        fields: List of field IDs or comma-separated string
    
    Returns:
        Response indicating streaming started
    """
    
    if isinstance(conids, list):
        conids = ",".join(map(str, conids))
    if isinstance(fields, list):
        fields = ",".join(map(str, fields))
    
    url = f"{BASE_URL}/iserver/marketdata/snapshot"
    params = {
        "conids": conids,
        "fields": fields
    }
    
    print(f"PRE-FLIGHT: Starting data stream for conids: {conids}")
    print(f"  Fields: {fields}\n")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        print("--- PRE-FLIGHT RESPONSE ---")
        print(json.dumps(result, indent=2))
        print("---------------------------\n")
        print("✓ Pre-flight complete. Data stream initialized.\n")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Pre-flight request failed: {e}\n")
        return False

def get_snapshot(conids):
    """Get market data snapshot after pre-flight has been established.
    
    Args:
        conids: List of contract IDs or comma-separated string
    
    Returns:
        List of market data snapshots
    """
    
    if isinstance(conids, list):
        conids = ",".join(map(str, conids))
    
    url = f"{BASE_URL}/iserver/marketdata/snapshot"
    params = {
        "conids": conids
    }
    
    print(f"SNAPSHOT: Requesting market data for conids: {conids}\n")
    
    try:
        response = requests.get(url, headers=get_headers("GET"), params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        print("--- SNAPSHOT RESPONSE ---")
        print(json.dumps(result, indent=2))
        print("------------------------\n")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Snapshot request failed: {e}\n")
        return None

if __name__ == "__main__":
    print("=" * 70)
    print("Testing Top-of-Book Snapshots with Pre-flight Request")
    print("=" * 70 + "\n")
    
    # Step 1: Check authentication
    if not check_auth_status():
        print("ERROR: Not authenticated. Cannot proceed.")
        exit(1)
    
    # Step 2: Define contracts and fields
    test_conids = [4521593, 780709675, 86656182, 4815747]
    
    # Field IDs:
    # 31 = Last Price
    # 84 = Bid Price
    # 86 = Ask Price
    # 85 = Bid Size
    # 88 = Ask Size
    # 7059 = Volume
    fields = [31, 84, 86, 85, 88, 7059]
    
    print("Test Contracts:")
    print("  - AZN (conid: 4521593)")
    print("  - B/Barrick (conid: 780709675)")
    print("  - IGLN (conid: 86656182)")
    print("  - NVDA (conid: 4815747)")
    print("\nRequested Fields:")
    print("  31 = Last Price")
    print("  84 = Bid Price")
    print("  86 = Ask Price")
    print("  85 = Bid Size")
    print("  88 = Ask Size")
    print("  7059 = Volume\n")
    
    print("=" * 70)
    print("Step 1: PRE-FLIGHT REQUEST")
    print("=" * 70 + "\n")
    
    # Make pre-flight request
    if not preflight_snapshot(test_conids, fields):
        print("Pre-flight failed. Exiting.")
        exit(1)
    
    print("=" * 70)
    print("Step 2: SNAPSHOT REQUEST (after pre-flight)")
    print("=" * 70 + "\n")
    
    # Get snapshot
    snapshot_data = get_snapshot(test_conids)
    
    if snapshot_data:
        print("=" * 70)
        print("PARSED DATA")
        print("=" * 70 + "\n")
        
        for item in snapshot_data:
            conid = item.get("conid")
            price = item.get("31")
            bid = item.get("84")
            ask = item.get("86")
            bid_size = item.get("85")
            ask_size = item.get("88")
            volume = item.get("7059")
            
            print(f"Conid {conid}:")
            print(f"  Last Price: {price}")
            print(f"  Bid: {bid} (size: {bid_size})")
            print(f"  Ask: {ask} (size: {ask_size})")
            print(f"  Volume: {volume}\n")
    
    print("=" * 70)
    print("Test complete!")
    print("=" * 70)
