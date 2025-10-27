#!/usr/bin/env python
"""Track live orders - simple order monitor"""

import os
from dotenv import load_dotenv
from ibkr_api import check_auth_status, get_live_orders

load_dotenv()

def print_orders(orders):
    """Print orders in a simple table."""
    if not orders:
        print("No orders found.\n")
        return
    
    print(f"\n{'Order ID':<15} {'Ticker':<8} {'Side':<6} {'Qty':<8} {'Filled':<8} {'Status':<20}")
    print("-" * 70)
    
    for order in orders:
        order_id = str(order.get("orderId", ""))[:14]
        ticker = order.get("ticker", "N/A")
        side = order.get("side", "N/A")
        qty = int(order.get("totalSize", 0))
        filled = int(order.get("filledQuantity", 0))
        status = order.get("status", "N/A")
        
        print(f"{order_id:<15} {ticker:<8} {side:<6} {qty:<8} {filled:<8} {status:<20}")
    
    print()

if __name__ == "__main__":
    print("=" * 70)
    print("Order Tracker")
    print("=" * 70 + "\n")
    
    if not check_auth_status():
        print("ERROR: Not authenticated.")
        exit(1)
    
    while True:
        print("\nOptions:")
        print("  1. View all orders")
        print("  2. View submitted orders")
        print("  3. View filled orders")
        print("  4. Refresh (force=true)")
        print("  5. Exit")
        
        choice = input("\nSelect (1-5): ").strip()
        
        if choice == "1":
            print("\n--- ALL ORDERS ---")
            orders = get_live_orders()
            print_orders(orders)
        
        elif choice == "2":
            print("\n--- SUBMITTED ORDERS ---")
            orders = get_live_orders(filters="submitted")
            print_orders(orders)
        
        elif choice == "3":
            print("\n--- FILLED ORDERS ---")
            orders = get_live_orders(filters="filled")
            print_orders(orders)
        
        elif choice == "4":
            print("\n--- REFRESHING (FORCE=TRUE) ---")
            orders = get_live_orders(force=True)
            print_orders(orders)
        
        elif choice == "5":
            print("Exiting.")
            break
        
        else:
            print("Invalid option.")

