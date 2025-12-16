#!/usr/bin/env python
"""
Show current position data (fetched from API)
Main fields: market name and value
"""

import sys
import os
import json

# Add project path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# Try to import; if it fails, print a helpful hint
try:
    from scripts.python.position_monitor import PositionManager
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("Please ensure all dependencies are installed and the virtual environment is activated")
    sys.exit(1)

def main():
    print("=" * 80)
    print("📊 Current position data (fetched from API)")
    print("=" * 80)
    print()

    try:
        pm = PositionManager()
        pm.load_positions()

        open_positions = [p for p in pm.positions if p.status == "open"]

        if not open_positions:
            print("❌ No open positions")
            return

        print(f"Total positions: {len(open_positions)}")
        print()
        print(f"{'Market':<60} {'Value (USDC)':>15} {'Quantity':>12} {'Price':>12}")
        print("-" * 100)

        positions_data = []
        total_value = 0

        for position in open_positions:
            # Fetch current price from API
            current_price = pm.get_current_price(position.token_id)
            if current_price is None:
                current_price = position.buy_price
                price_source = "Local (API fetch failed)"
            else:
                price_source = "API"

            # Fetch actual quantity from blockchain API
            actual_quantity = pm.get_token_balance(position.token_id, wallet="both")
            if actual_quantity > 0.0001:
                quantity = round(actual_quantity, 6)
                quantity_source = "API"
            else:
                quantity = position.quantity
                quantity_source = "Local"

            # Calculate value: API price × API quantity
            value = round(current_price * quantity, 6)
            total_value += value

            market_name = position.market_question
            if len(market_name) > 58:
                market_name = market_name[:55] + "..."

            position_info = {
                "market_question": position.market_question,
                "value": value,
                "quantity": quantity,
                "current_price": current_price,
                "quantity_source": quantity_source,
                "price_source": price_source,
                "token_id": position.token_id[:20] + "..."
            }

            positions_data.append(position_info)

            print(f"{market_name:<60} ${value:>14.4f} {quantity:>12.6f} ${current_price:>11.4f} ({price_source})")

        print("-" * 100)
        print(f"{'Total':<60} ${total_value:>14.4f}")
        print()

        # Output JSON data
        print("=" * 80)
        print("📋 JSON data (market name and value only)")
        print("=" * 80)

        # Output only the main fields
        simplified_data = [
            {
                "market": pos["market_question"],
                "value": pos["value"]
            }
            for pos in positions_data
        ]

        print(json.dumps(simplified_data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
