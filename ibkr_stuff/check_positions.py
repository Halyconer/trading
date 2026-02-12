#!/usr/bin/env python
"""Check current positions in your IBKR account"""

import os
from dotenv import load_dotenv
from ibkr_api import check_auth_status, get_account_ids, get_positions

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    print("=" * 70)
    print("Check Positions Tool")
    print("=" * 70 + "\n")
    
    # Step 1: Check authentication
    if not check_auth_status():
        print("ERROR: Not authenticated. Cannot proceed.")
        exit(1)
    
    # Step 2: Get account ID (either from .env or from API)
    account_id = os.getenv("ACCOUNT_ID")
    
    if not account_id:
        print("\nNo account ID in .env, fetching from API...")
        account_id = get_account_ids()
    
    if not account_id:
        print("ERROR: Could not determine account ID.")
        exit(1)
    
    print(f"\n✓ Using account: {account_id}\n")
    
    # Step 3: Fetch positions
    print("=" * 70)
    print("Fetching positions for: AZN, B, IGLN, NVDA")
    print("=" * 70 + "\n")
    
    # Define which positions to check (your 4 stocks)
    conids = [851181134, 780709675, 86656182, 4815747]  # AZN, B, IGLN, NVDA
    
    positions = get_positions(account_id, conids=conids)
    
    if positions:
        print("\n" + "=" * 70)
        print("✓ Positions retrieved successfully!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("No positions found or error occurred")
        print("=" * 70)
