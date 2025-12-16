#!/usr/bin/env python
"""
Show current position data (fetched from API)
Main fields: market name and value
Simplified version: read local file directly and display
"""

import json
import os
from pathlib import Path

def main():
    # Read positions file
    positions_file = Path(__file__).parent / "positions.json"

    if not positions_file.exists():
        print("❌ Positions file does not exist")
        return

    with open(positions_file, 'r', encoding='utf-8') as f:
        all_positions = json.load(f)

    # Filter open positions
    open_positions = [p for p in all_positions if p.get('status') == 'open']

    print("=" * 80)
    print("📊 Current position data")
    print("=" * 80)
    print(f"Total positions: {len(all_positions)} (open: {len(open_positions)})")
    print()

    if not open_positions:
        print("❌ No open positions")
        return

    # Output main fields (market name and value)
    positions_output = []

    for position in open_positions:
        market_name = position.get('market_question', '')
        quantity = position.get('quantity', 0)
        buy_price = position.get('buy_price', 0)

        # Calculate value (using buy price; in practice should fetch current price from API)
        # Using buy price for now; in real usage should fetch current price from API
        value = round(buy_price * quantity, 2)

        positions_output.append({
            "market": market_name,
            "value": value
        })

    print("📋 JSON data (market name and value)")
    print("=" * 80)
    print(json.dumps(positions_output, indent=2, ensure_ascii=False))
    print()
    print("=" * 80)
    print("⚠️  Note: this value is computed from the buy price; actual value should be computed using the current API price")

if __name__ == "__main__":
    main()
