"""
Test script: find Solana Up or Down markets
Test whether we can find the user-provided market: sol-updown-15m-1764972900
"""

import json
import os
import sys
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, PROJECT_ROOT)

from agents.polymarket.gamma import GammaMarketClient

load_dotenv()


def find_solana_market_by_slug_pattern(gamma, slug_pattern="sol-updown-15m"):
    """Find Solana markets by slug pattern."""
    print(f"🔍 Searching for markets containing '{slug_pattern}'...")

    # Fetch all active markets
    markets = gamma.get_all_current_markets(limit=500)
    print(f"   Found {len(markets)} active markets")

    matches = []
    for market in markets:
        slug = market.get('slug', '').lower()
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()

        # Check whether slug or question contains the pattern
        if (slug_pattern.lower() in slug or
            slug_pattern.lower() in question or
            'solana up or down' in question or
            'sol up or down' in question):

            matches.append({
                'id': market.get('id'),
                'slug': market.get('slug'),
                'question': market.get('question'),
                'active': market.get('active'),
                'closed': market.get('closed'),
                'enableOrderBook': market.get('enableOrderBook'),
                'clobTokenIds': market.get('clobTokenIds'),
                'description': market.get('description', '')[:100]
            })

    return matches


def find_solana_market_by_keywords(gamma):
    """Find Solana markets by keywords (using existing logic)."""
    print(f"🔍 Searching Solana Up or Down markets using keywords...")

    search_keywords = [
        "solana up or down",
        "solana up/down",
        "sol up or down",
        "sol up/down"
    ]

    markets = gamma.get_all_current_markets(limit=500)
    print(f"   Found {len(markets)} active markets")

    matches = []
    for market in markets:
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        slug = market.get('slug', '').lower()

        text_to_check = f"{question} {description} {slug}"

        for keyword in search_keywords:
            if keyword in text_to_check:
                if (market.get('active', False) and
                    not market.get('closed', False) and
                    market.get('enableOrderBook', False)):

                    matches.append({
                        'id': market.get('id'),
                        'slug': market.get('slug'),
                        'question': market.get('question'),
                        'active': market.get('active'),
                        'closed': market.get('closed'),
                        'enableOrderBook': market.get('enableOrderBook'),
                        'clobTokenIds': market.get('clobTokenIds'),
                        'description': market.get('description', '')[:100]
                    })
                    break

    return matches


def main():
    print("=" * 70)
    print("🧪 Test Solana market search")
    print("=" * 70)

    gamma = GammaMarketClient()

    # Method 1: search by slug pattern
    print("\nMethod 1: Search by slug pattern")
    print("-" * 70)
    matches1 = find_solana_market_by_slug_pattern(gamma, "sol-updown-15m")

    if matches1:
        print(f"✅ Found {len(matches1)} matching markets:")
        for i, m in enumerate(matches1, 1):
            print(f"\n  Market {i}:")
            print(f"    ID: {m['id']}")
            print(f"    Slug: {m['slug']}")
            print(f"    Question: {m['question'][:60]}...")
            print(f"    Active: {m['active']}")
            print(f"    Closed: {m['closed']}")
            print(f"    Order book enabled: {m['enableOrderBook']}")
            if m.get('clobTokenIds'):
                token_ids = json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'], str) else m['clobTokenIds']
                print(f"    Token IDs: {token_ids}")
    else:
        print("❌ No matching markets found")

    # Method 2: search by keywords (existing logic)
    print("\nMethod 2: Search by keywords (existing logic)")
    print("-" * 70)
    matches2 = find_solana_market_by_keywords(gamma)

    if matches2:
        print(f"✅ Found {len(matches2)} matching markets:")
        for i, m in enumerate(matches2, 1):
            print(f"\n  Market {i}:")
            print(f"    ID: {m['id']}")
            print(f"    Slug: {m['slug']}")
            print(f"    Question: {m['question'][:60]}...")
            print(f"    Active: {m['active']}")
            print(f"    Closed: {m['closed']}")
            print(f"    Order book enabled: {m['enableOrderBook']}")
            if m.get('clobTokenIds'):
                token_ids = json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'], str) else m['clobTokenIds']
                print(f"    Token IDs: {token_ids}")
    else:
        print("❌ No matching markets found")

    # Merge results and deduplicate
    all_matches = []
    seen_ids = set()
    for m in matches1 + matches2:
        if m['id'] not in seen_ids:
            all_matches.append(m)
            seen_ids.add(m['id'])

    print("\n" + "=" * 70)
    print(f"📊 Summary: found {len(all_matches)} unique Solana Up or Down markets")
    print("=" * 70)

    if all_matches:
        print("\nAll found markets:")
        for i, m in enumerate(all_matches, 1):
            print(f"  {i}. {m['question'][:50]}... (Slug: {m['slug']})")
    else:
        print("\n⚠️  No Solana Up or Down markets found")
        print("   Possible reasons:")
        print("   1. There is currently no open Solana market")
        print("   2. The market is closed or archived")
        print("   3. Search keywords need adjustment")


if __name__ == "__main__":
    main()
