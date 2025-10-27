#!/usr/bin/env python
"""Place market orders for AZN, B, IGLN, NVDA"""

import os
import time
from dotenv import load_dotenv
from ibkr_api import check_auth_status, get_account_ids, place_market_order, confirm_order_reply

# Load environment variables
load_dotenv()

def handle_order_reply(reply_data):
    """Handle order reply messages and confirmations.
    
    Args:
        reply_data: The response from place_market_order which may contain a reply message
    
    Returns:
        True if order was confirmed, False if cancelled or no action needed
    """
    if not reply_data:
        return False
    
    # Check if this is a list response
    if isinstance(reply_data, list) and len(reply_data) > 0:
        reply_data = reply_data[0]
    
    # Check for reply message that requires confirmation
    if isinstance(reply_data, dict):
        # Case 1: Message confirmation needed (e.g., "without market data" warning)
        if "message" in reply_data:
            reply_id = reply_data.get("id")
            messages = reply_data.get("message", [])
            
            if reply_id and messages:
                print(f"\n⚠️  ORDER CONFIRMATION REQUIRED:")
                for msg in messages:
                    print(f"   {msg}")
                
                confirm = input("\nConfirm this order? (yes/no): ").strip().lower()
                
                if confirm == "yes":
                    result = confirm_order_reply(reply_id, confirmed=True)
                    return result is not None
                else:
                    confirm_order_reply(reply_id, confirmed=False)
                    return False
        
        # Case 2: Order already submitted successfully
        if "order_id" in reply_data or "order_status" in reply_data:
            return True
    
    return False

if __name__ == "__main__":
    print("=" * 70)
    print("Market Order Placement Tool")
    print("=" * 70 + "\n")
    
    # Step 1: Check authentication
    if not check_auth_status():
        print("ERROR: Not authenticated. Cannot proceed.")
        exit(1)
    
    # Step 2: Get account ID 
    account_id = os.getenv("ACCOUNT_ID")
    
    if not account_id:
        print("ERROR: Could not determine account ID.")
        exit(1)
    
    print(f"\n✓ Using account: {account_id}\n")
    
    # Step 3: Define orders
    # Format: conid, symbol, cash amount
    orders = [
        # {"conid": 4521593, "side": "BUY", "cashQty": 1000, "symbol": "AZN"},
        {"conid": 780709675, "side": "BUY", "cashQty": 1000, "symbol": "B"},
        {"conid": 86656182, "side": "BUY", "cashQty": 1000, "symbol": "IGLN"},
        {"conid": 4815747, "side": "BUY", "cashQty": 1000, "symbol": "NVDA"},
    ]
    
    print("=" * 70)
    print("Orders to place:")
    print("=" * 70)
    for order in orders:
        print(f"  {order['symbol']}: ${order['cashQty']} ({order['side']})")
    print()
    
    # Step 4: Confirm before placing
    confirm = input("Place these orders? (yes/no): ").strip().lower()
    
    if confirm != "yes":
        print("Orders cancelled.")
        exit(0)
    
    # Step 5: Place orders
    print("\n" + "=" * 70)
    print("Placing orders...")
    print("=" * 70 + "\n")
    
    results = []
    for i, order in enumerate(orders, 1):
        print(f"\n--- Order {i}/{len(orders)}: {order['symbol']} ---")
        reply = place_market_order(
            account_id,
            conid=order["conid"],
            side=order["side"],
            cash_qty=order["cashQty"]
        )
        
        # Handle any reply messages that require confirmation
        success = handle_order_reply(reply)
        results.append(success)
        
        # Small delay between orders
        if i < len(orders):
            time.sleep(1)
    
    # Summary
    successful = sum(1 for r in results if r)
    print("\n" + "=" * 70)
    print(f"Order Summary: {successful}/{len(orders)} successful")
    print("=" * 70)
