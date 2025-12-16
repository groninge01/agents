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
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

def main():
    print("=" * 80)
    print("📊 Current position data (fetched from API)")
    print("=" * 80)
    print()

    try:
        from scripts.python.position_monitor import PositionManager

        pm = PositionManager()
        pm.load_positions()

        open_positions = [p for p in pm.positions if p.status == "open"]

        if not open_positions:
            print("❌ No open positions")
            return

        print(f"Total positions: {len(open_positions)}")
        print()

        positions_data = []
        total_value = 0

        for i, position in enumerate(open_positions, 1):
            print(f"[{i}/{len(open_positions)}] Fetching data for {position.market_question[:50]}...")

            # Fetch current price from API (order book API)
            current_price = pm.get_current_price(position.token_id)
            if current_price is None:
                current_price = position.buy_price
                price_source = "Local (API fetch failed)"
            else:
                price_source = "API (order book)"

            # Fetch actual quantity from blockchain API
            try:
                actual_quantity = pm.get_token_balance(position.token_id, wallet="both")
                if actual_quantity > 0.0001:
                    quantity = round(actual_quantity, 6)
                    quantity_source = "API (blockchain)"
                else:
                    quantity = position.quantity
                    quantity_source = "Local"
            except Exception as e:
                quantity = position.quantity
                quantity_source = "Local (error)"

            # Calculate value: API price × API quantity
            value = round(current_price * quantity, 6)
            total_value += value

            position_info = {
                "market": position.market_question,
                "shares": round(quantity, 6),  # Position size
                "value": round(value, 2)  # Current value (keep 2 decimals to match UI display)
            }

            positions_data.append(position_info)

            print(f"   ✅ {position.market_question[:60]}")
            print(f"      Shares: {quantity:.6f} | Value: ${value:.2f} | Price: ${current_price:.4f} ({price_source})")
            print()

        print("=" * 80)
        print(f"📊 Summary: Total Value = ${total_value:.2f}")
        print("=" * 80)
        print()

        # Output JSON data (market name, shares, and value)
        print("=" * 80)
        print("📋 JSON data (market name, shares, and current value)")
        print("=" * 80)
        print(json.dumps(positions_data, indent=2, ensure_ascii=False))

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("Please ensure all dependencies are installed and the virtual environment is activated")
        print("Run: source .venv/bin/activate")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
