"""
Buy markets by category
Supports filtering markets by tags and buying by category
"""

import json
import os
import re
from dotenv import load_dotenv
from agents.polymarket.gamma import GammaMarketClient
from agents.polymarket.polymarket import Polymarket
from agents.application.executor import Executor
from langchain_core.messages import HumanMessage

load_dotenv()


def find_markets_by_category(gamma, executor, categories, min_liquidity=5000, count_per_category=3):
    """Use AI to filter markets by category."""
    markets = gamma.get_all_current_markets(limit=200)

    # Pre-filter: liquidity and price
    candidates = []
    for m in markets:
        liquidity = float(m.get('liquidity', 0) or 0)
        prices = m.get('outcomePrices', [])
        if isinstance(prices, str):
            prices = json.loads(prices)

        yes_price = float(prices[0]) if prices else 0.5

        if liquidity > min_liquidity and 0.1 <= yes_price <= 0.9:
            candidates.append({
                'question': m.get('question', ''),
                'liquidity': liquidity,
                'yes_price': yes_price,
                'market': m
            })

    print(f"   Pre-filter: {len(candidates)} high-liquidity markets")

    # Sort by liquidity; take top 50
    candidates.sort(key=lambda x: x['liquidity'], reverse=True)
    candidates = candidates[:50]

    # AI categorization
    results = {cat: [] for cat in categories}

    print(f"\n🤖 AI categorizing markets...")

    # Build market list
    market_list = [f"{i+1}. {m['question']}" for i, m in enumerate(candidates)]

    prompt = f'''You are a market categorization expert. Here is a list of prediction markets:

{chr(10).join(market_list[:30])}  # Up to 30

Please categorize these markets into: {', '.join(categories)}

Return format (one per line):
<category>: <market_number>,<market_number>,...

Example:
finance: 1,3,5
culture: 2,7,9'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    response = result.content

    print("AI categorization result:")
    print(response)
    print()

    # Parse AI categorization result
    for cat in categories:
        pattern = rf'{cat}[:\s]+([0-9,\s]+)'
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            indices_str = match.group(1)
            indices = [int(i.strip())-1 for i in re.findall(r'\d+', indices_str)]

            for idx in indices:
                if 0 <= idx < len(candidates):
                    results[cat].append(candidates[idx])
                    if len(results[cat]) >= count_per_category * 2:
                        break

    return results


def ai_select_from_category(executor, candidates, category, count=3):
    """AI selects markets from a category."""
    if not candidates:
        return []

    market_list = []
    for i, m in enumerate(candidates[:20], 1):  # Show up to 20
        market_list.append(f"{i}. {m['question']} (Yes:{m['yes_price']:.0%}, Liquidity:\${m['liquidity']/1000:.0f}k)")

    prompt = f'''You are a professional forecaster in the {category} domain. Here are markets in the {category} category:

{chr(10).join(market_list)}

Select {count} markets you are most confident forecasting.
Reply with market numbers only, comma-separated. Example: 1,3,5'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    selection = result.content

    # Parse selection
    indices = re.findall(r'\d+', selection)
    indices = [int(i)-1 for i in indices if int(i)-1 < len(candidates)][:count]

    return [candidates[i] for i in indices]


def analyze_and_trade(executor, polymarket, market_info, amount):
    """Analyze and trade a single market."""
    question = market_info['question']
    yes_price = market_info['yes_price']

    # AI forecast
    prompt = f'''Analyze: {question}
Current Yes price: {yes_price:.0%}

What do you think the true probability of Yes is? Reply with a single number (0-1), e.g. 0.65'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])

    # Parse probability
    try:
        ai_prob = float(re.search(r'0?\.\d+', result.content).group())
    except:
        ai_prob = 0.5

    # Decide buy side
    if ai_prob > yes_price + 0.05:
        side = 'Yes'
        edge = ai_prob - yes_price
    elif ai_prob < yes_price - 0.05:
        side = 'No'
        edge = yes_price - ai_prob
    else:
        side = 'Yes' if ai_prob >= 0.5 else 'No'
        edge = abs(ai_prob - yes_price)

    print(f"   AI forecast: {ai_prob:.0%} | Buy: {side} | Edge: {edge:.0%}")

    # Get token_id
    market = market_info['market']
    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        token_ids = json.loads(token_ids)

    token_idx = 0 if side == 'Yes' else 1
    token_id = token_ids[token_idx] if token_ids else None

    if not token_id:
        print(f"   ❌ Unable to get token_id")
        return None

    # Get price
    try:
        orderbook = polymarket.client.get_order_book(token_id)
        if orderbook and orderbook.asks:
            best_ask = min(orderbook.asks, key=lambda x: float(x.price))
            buy_price = float(best_ask.price)
        else:
            print(f"   ❌ Unable to fetch order book")
            return None

        # Calculate quantity
        min_amount = max(amount, 1.05)
        quantity = min_amount / buy_price
        quantity = round(quantity, 2)

        print(f"   Price: ${buy_price:.4f} | Quantity: {quantity:.2f}")

        # Execute buy order
        result = polymarket.execute_order(
            price=buy_price,
            size=quantity,
            side="BUY",
            token_id=token_id
        )

        order_id = result.get('orderID', result.get('id', '')) if isinstance(result, dict) else str(result)

        print(f"   ✅ Buy successful! Order: {order_id[:20]}...")

        return {
            'question': question,
            'side': side,
            'token_id': token_id,
            'buy_price': buy_price,
            'quantity': quantity,
            'cost': buy_price * quantity,
            'order_id': order_id,
            'ai_prob': ai_prob
        }

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def main(categories=['finance', 'culture'], count_per_category=3, amount_per_trade=1.0):
    """Main."""
    print("=" * 70)
    print("🎯 Buy markets by category")
    print("=" * 70)
    print(f"Categories: {', '.join(categories)}")
    print(f"Markets per category: {count_per_category}")
    print(f"Amount per trade: ${amount_per_trade}")
    print(f"Total investment: ${len(categories) * count_per_category * amount_per_trade}")
    print("=" * 70)

    # Init
    gamma = GammaMarketClient()
    polymarket = Polymarket()
    executor = Executor()

    # Check balance
    balance = polymarket.get_usdc_balance()
    print(f"\n💳 Wallet balance: ${balance:.2f}")

    total_needed = len(categories) * count_per_category * amount_per_trade
    if balance < total_needed:
        print(f"❌ Insufficient balance! Need ${total_needed:.2f}")
        return

    # Find markets
    print(f"\n📊 Finding markets...")
    category_markets = find_markets_by_category(gamma, executor, categories, count_per_category=count_per_category)

    for cat, markets in category_markets.items():
        print(f"   {cat}: found {len(markets)}")

    # AI selection
    print(f"\n🤖 AI selecting best markets...")
    selected_markets = {}

    for cat in categories:
        if category_markets[cat]:
            selected = ai_select_from_category(executor, category_markets[cat], cat, count_per_category)
            selected_markets[cat] = selected
            print(f"   {cat}: selected {len(selected)}")
        else:
            print(f"   ⚠️ {cat}: no markets found that meet criteria")
            selected_markets[cat] = []

    # Trading
    print(f"\n" + "=" * 70)
    print("🚀 Starting trades")
    print("=" * 70)

    successful_trades = []

    for cat in categories:
        if not selected_markets[cat]:
            continue

        print(f"\n📁 {cat.upper()} category:")
        print("-" * 70)

        for i, market_info in enumerate(selected_markets[cat], 1):
            print(f"\n[{i}/{len(selected_markets[cat])}] {market_info['question'][:50]}...")
            trade = analyze_and_trade(executor, polymarket, market_info, amount_per_trade)

            if trade:
                successful_trades.append(trade)

    # Add to monitor
    if successful_trades:
        print(f"\n" + "=" * 70)
        print(f"✅ Purchase complete: {len(successful_trades)} markets")
        print("=" * 70)

        from scripts.python.position_monitor import PositionManager
        pm = PositionManager()

        print(f"\n📋 Adding to position monitor...")
        for trade in successful_trades:
            position, is_new = pm.add_position(
                token_id=trade['token_id'],
                market_question=trade['question'],
                side=trade['side'],
                buy_price=trade['buy_price'],
                quantity=trade['quantity'],
                cost=trade['cost'],
                order_id=trade.get('order_id', '')
            )
            if is_new:
                print(f"   ✅ {trade['question'][:40]}... | {trade['side']}")

        print(f"\n" + "=" * 70)
        print("💡 Start monitoring:")
        print("   ./scripts/bash/restart_monitor_autosell.sh")
        print("=" * 70)
    else:
        print("\n❌ No successful trades")


if __name__ == "__main__":
    import sys

    # Default parameters
    categories = ['finance', 'culture']
    count = 3
    amount = 1.0

    # Simple arg parsing
    if len(sys.argv) > 1:
        # Example: python buy_by_category.py finance,culture 3 1.0
        if len(sys.argv) >= 3:
            categories = sys.argv[1].split(',')
        if len(sys.argv) >= 4:
            count = int(sys.argv[2])
        if len(sys.argv) >= 5:
            amount = float(sys.argv[3])

    main(categories=categories, count_per_category=count, amount_per_trade=amount)
