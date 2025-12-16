"""
Test market mapping utilities
Used to verify whether the Yes/No mapping is correct for markets like Seahawks vs. Falcons
"""

import sys
import os

# Add project root to Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

from agents.polymarket.gamma import GammaMarketClient
from scripts.python.market_utils import get_market_info, get_price_for_side, get_token_id_for_side


def find_seahawks_falcons_market():
    """Find the Seahawks vs. Falcons market."""
    gamma = GammaMarketClient()
    markets = gamma.get_all_current_markets(limit=500)

    for market in markets:
        question = market.get('question', '').lower()
        if 'seahawks' in question and 'falcons' in question:
            return market

    return None


def test_market_mapping():
    """Test market mapping."""
    print("=" * 70)
    print("🔍 Test market mapping utilities")
    print("=" * 70)

    # Find Seahawks vs. Falcons market
    print("\nFinding Seahawks vs. Falcons market...")
    market = find_seahawks_falcons_market()

    if not market:
        print("❌ Seahawks vs. Falcons market not found")
        print("Trying to find another sports market...")

        # Find any sports market
        gamma = GammaMarketClient()
        markets = gamma.get_all_current_markets(limit=100)

        sports_keywords = ['win', 'vs', 'beat', 'defeat', 'game', 'match']
        for m in markets:
            question = m.get('question', '').lower()
            if any(keyword in question for keyword in sports_keywords):
                market = m
                print(f"Found market: {m.get('question', '')[:60]}...")
                break

        if not market:
            print("❌ No suitable test market found")
            return

    print(f"✅ Found market: {market.get('question', '')}")
    print()

    # Get raw data
    outcomes = market.get('outcome', []) or market.get('outcomes', [])
    if isinstance(outcomes, str):
        import json
        try:
            outcomes = json.loads(outcomes)
        except:
            outcomes = []

    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        import json
        try:
            prices = json.loads(prices)
        except:
            prices = []

    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        import json
        try:
            token_ids = json.loads(token_ids)
        except:
            token_ids = []

    print("Raw data:")
    print(f"  Outcomes: {outcomes}")
    print(f"  Prices: {prices}")
    print(f"  Token IDs: {token_ids}")
    print()

    # Use utility function to get mapping info
    market_info = get_market_info(market)

    print("Mapping result:")
    print(f"  Yes maps to: {market_info['yes_outcome']} (Price: {market_info['yes_price']:.4f}, Token: {market_info['yes_token_id']})")
    print(f"  No maps to:  {market_info['no_outcome']} (Price: {market_info['no_price']:.4f}, Token: {market_info['no_token_id']})")
    print(f"  Mapping index: {market_info['mapping']}")
    print()

    # Validate mapping
    print("Validation:")
    yes_price_direct = get_price_for_side(market, 'Yes')
    no_price_direct = get_price_for_side(market, 'No')
    yes_token_direct = get_token_id_for_side(market, 'Yes')
    no_token_direct = get_token_id_for_side(market, 'No')

    print(f"  get_price_for_side(market, 'Yes'): {yes_price_direct}")
    print(f"  get_price_for_side(market, 'No'): {no_price_direct}")
    print(f"  get_token_id_for_side(market, 'Yes'): {yes_token_direct}")
    print(f"  get_token_id_for_side(market, 'No'): {no_token_direct}")
    print()

    # Check whether prices are reasonable (should sum to about 1)
    total_price = (yes_price_direct or 0) + (no_price_direct or 0)
    print(f"  Price sum: {total_price:.4f} (should be close to 1.0)")

    if abs(total_price - 1.0) > 0.1:
        print("  ⚠️ Warning: price sum deviates significantly from 1.0; mapping may be incorrect")
    else:
        print("  ✅ Price sum looks reasonable")

    print("=" * 70)


if __name__ == "__main__":
    test_market_mapping()
