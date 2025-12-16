"""
Solana Up or Down market buying script
Markets open every 15 minutes; poll every second to check when the market is open
Buy immediately once it opens
"""

import json
import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

from agents.polymarket.gamma import GammaMarketClient
from agents.polymarket.polymarket import Polymarket
from scripts.python.position_monitor import PositionManager

load_dotenv()


def find_solana_market(gamma):
    """Find the Solana Up or Down market."""
    # Search keywords
    search_keywords = [
        "solana up or down",
        "solana up/down",
        "sol up or down",
        "sol up/down"
    ]

    # Slug patterns (used to match market identifiers in URL)
    slug_patterns = [
        "sol-updown-15m",  # e.g.: sol-updown-15m-1764972900
        "sol-updown",
        "solana-updown"
    ]

    # Fetch all active markets
    markets = gamma.get_all_current_markets(limit=500)

    for market in markets:
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        slug = market.get('slug', '').lower()

        # Check whether it matches Solana Up or Down
        text_to_check = f"{question} {description} {slug}"

        # Method 1: keyword search
        for keyword in search_keywords:
            if keyword in text_to_check:
                # Check whether market is active and tradable
                if (market.get('active', False) and
                    not market.get('closed', False) and
                    market.get('enableOrderBook', False)):
                    return market

        # Method 2: slug pattern search (more precise)
        for pattern in slug_patterns:
            if pattern in slug:
                # Check whether market is active and tradable
                if (market.get('active', False) and
                    not market.get('closed', False) and
                    market.get('enableOrderBook', False)):
                    return market

    return None


def buy_solana_market(polymarket, market, amount=1.0, side='Yes', dry_run=False):
    """Buy the Solana market."""
    try:
        question = market.get('question', '')
        print(f"📋 Market: {question[:60]}...")

        # Get token IDs
        token_ids = market.get('clobTokenIds', [])
        if isinstance(token_ids, str):
            token_ids = json.loads(token_ids)

        if not token_ids or len(token_ids) < 2:
            print(f"   ❌ Unable to get token IDs")
            return None

        # Yes = token_ids[0], No = token_ids[1]
        token_idx = 0 if side == 'Yes' else 1
        token_id = token_ids[token_idx]

        # Get current price
        orderbook = polymarket.client.get_order_book(token_id)
        if not orderbook or not orderbook.asks:
            print(f"   ❌ Unable to get order book (market may not be open yet)")
            return None

        # Buy uses ask price (lowest ask)
        best_ask = min(orderbook.asks, key=lambda x: float(x.price))
        buy_price = float(best_ask.price)

        # Calculate quantity
        min_amount = max(amount, 1.05)  # At least $1.05
        quantity = min_amount / buy_price
        quantity = round(quantity, 2)

        print(f"   Side: {side}")
        print(f"   Price: ${buy_price:.4f}")
        print(f"   Quantity: {quantity:.2f}")
        print(f"   Amount: ${min_amount:.2f}")

        if dry_run:
            print(f"   📋 Dry run - no real trade executed")
            return {
                'question': question,
                'side': side,
                'token_id': token_id,
                'buy_price': buy_price,
                'quantity': quantity,
                'cost': min_amount,
                'order_id': 'simulated'
            }

        # Execute limit order
        result = polymarket.execute_order(
            price=buy_price,
            size=quantity,
            side="BUY",
            token_id=token_id
        )

        # Extract order ID
        order_id = result.get('orderID', result.get('id', '')) if isinstance(result, dict) else str(result)

        print(f"   ✅ BUY {side} ${amount} successful!")
        print(f"   Order ID: {order_id[:20]}..." if len(order_id) > 20 else f"   Order ID: {order_id}")

        return {
            'question': question,
            'side': side,
            'token_id': token_id,
            'buy_price': buy_price,
            'quantity': quantity,
            'cost': min_amount,
            'order_id': order_id
        }

    except Exception as e:
        print(f"   ❌ Buy failed: {e}")
        return None


def poll_and_buy_solana(gamma, polymarket, amount=1.0, side='Yes', dry_run=False, max_wait_minutes=15):
    """
    Poll to check whether the Solana market is open, and buy immediately once open.

    Args:
        gamma: GammaMarketClient instance
        polymarket: Polymarket instance
        amount: Buy amount
        side: Side ('Yes' or 'No')
        dry_run: Dry run
        max_wait_minutes: Max wait time (minutes)
    """
    print("=" * 70)
    print("🔍 Solana Up or Down market polling & buy")
    print("=" * 70)
    print(f"💰 Amount: ${amount}")
    print(f"📊 Side: {side}")
    print(f"🔒 Mode: {'Dry run' if dry_run else '⚠️ LIVE TRADE'}")
    print(f"⏰ Max wait time: {max_wait_minutes} minutes")
    print("=" * 70)

    start_time = datetime.now()
    max_wait_seconds = max_wait_minutes * 60
    check_count = 0

    while True:
        check_count += 1
        elapsed = (datetime.now() - start_time).total_seconds()

        # Check timeout
        if elapsed > max_wait_seconds:
            print(f"\n⏰ Timeout! Waited {max_wait_minutes} minutes, no open market found")
            return None

        # Find market
        print(f"\n[{check_count}] Checking Solana market... (waited {elapsed:.0f}s)")
        market = find_solana_market(gamma)

        if market:
            # Check whether market is tradable (has order book)
            token_ids = market.get('clobTokenIds', [])
            if isinstance(token_ids, str):
                token_ids = json.loads(token_ids)

            if token_ids and len(token_ids) >= 2:
                token_id = token_ids[0] if side == 'Yes' else token_ids[1]

                try:
                    # Try to fetch order book
                    orderbook = polymarket.client.get_order_book(token_id)

                    if orderbook and orderbook.asks:
                        print(f"✅ Found an open Solana market!")
                        print(f"   Question: {market.get('question', '')[:60]}...")

                        # Buy
                        result = buy_solana_market(polymarket, market, amount, side, dry_run)

                        if result:
                            # Add to position monitor
                            if not dry_run:
                                print("\n📋 Adding to position monitor...")
                                pm = PositionManager()
                                pm.add_position(
                                    token_id=result['token_id'],
                                    market_question=result['question'],
                                    side=result['side'],
                                    buy_price=result['buy_price'],
                                    quantity=result['quantity'],
                                    cost=result['cost'],
                                    order_id=result['order_id']
                                )
                                print(f"   ✅ Added to position monitor")

                            return result

                except Exception as e:
                    # Market may not be fully open yet; continue waiting
                    pass

        # Wait 1 second and check again
        time.sleep(1)


if __name__ == "__main__":
    import sys

    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--execute':
        dry_run = False

    gamma = GammaMarketClient()
    polymarket = Polymarket()

    poll_and_buy_solana(
        gamma=gamma,
        polymarket=polymarket,
        amount=1.0,
        side='Yes',
        dry_run=dry_run,
        max_wait_minutes=15
    )
