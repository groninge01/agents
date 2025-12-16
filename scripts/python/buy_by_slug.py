"""
Buy precisely by market slug
Get slug from the Polymarket webpage URL, for example:
https://polymarket.com/event/fed-decision-in-october
                            ↑
                        slug: fed-decision-in-october
"""

import json
import sys
import re
from agents.polymarket.gamma import GammaMarketClient
from agents.polymarket.polymarket import Polymarket
from agents.application.executor import Executor
from scripts.python.position_monitor import PositionManager
from langchain_core.messages import HumanMessage


def buy_market_by_slug(polymarket, executor, slug, amount=1.0):
    """Buy a market by slug."""
    gamma = GammaMarketClient()

    # Fetch market data
    try:
        # Try as event slug
        markets = gamma.get_event(slug)
        if not markets:
            # Try as market slug
            markets = [gamma.get_market(slug)]
    except:
        print(f"   ❌ Unable to find market: {slug}")
        return None

    if not markets or not markets[0]:
        print(f"   ❌ Unable to find market: {slug}")
        return None

    market = markets[0]
    question = market.get('question', '')

    print(f"   📋 {question[:50]}...")

    # AI analysis
    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        prices = json.loads(prices)
    yes_price = float(prices[0]) if prices else 0.5

    prompt = f'''Analyze: {question}
Current Yes price: {yes_price:.0%}

What do you think the true probability of Yes is? Return only a number (0-1), e.g.: 0.65'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])

    # Parse probability
    try:
        ai_prob = float(re.search(r'0?\.\d+', result.content).group())
    except:
        ai_prob = 0.5

    # Decide buy side
    if ai_prob > yes_price + 0.05:
        side = 'Yes'
    elif ai_prob < yes_price - 0.05:
        side = 'No'
    else:
        side = 'Yes' if ai_prob >= 0.5 else 'No'

    print(f"   AI forecast: {ai_prob:.0%} | Market: {yes_price:.0%} | Buy: {side}")

    # Get token_id
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
            buy_price = yes_price if side == 'Yes' else (1 - yes_price)

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

        print(f"   ✅ Buy successful!")

        return {
            'question': question,
            'side': side,
            'token_id': token_id,
            'buy_price': buy_price,
            'quantity': quantity,
            'cost': buy_price * quantity,
            'order_id': order_id
        }

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def main(slugs, amount_per_trade=1.0):
    """Main function."""
    print("=" * 70)
    print("🎯 Buy precisely by slug")
    print("=" * 70)
    print(f"Number of markets: {len(slugs)}")
    print(f"Amount per trade: ${amount_per_trade}")
    print(f"Total investment: ${len(slugs) * amount_per_trade}")
    print("=" * 70)

    # Initialize
    polymarket = Polymarket()
    executor = Executor()

    # Check balance
    balance = polymarket.get_usdc_balance()
    print(f"\n💳 Wallet balance: ${balance:.2f}")

    total_needed = len(slugs) * amount_per_trade
    if balance < total_needed:
        print(f"❌ Insufficient balance! Need ${total_needed:.2f}")
        return

    # Buy
    print(f"\n🚀 Starting purchases...")
    print()

    successful_trades = []

    for i, slug in enumerate(slugs, 1):
        print(f"[{i}/{len(slugs)}] {slug}")
        trade = buy_market_by_slug(polymarket, executor, slug, amount_per_trade)

        if trade:
            successful_trades.append(trade)
        print()

    # Add to monitor
    if successful_trades:
        print("=" * 70)
        print(f"✅ Purchases complete: {len(successful_trades)}/{len(slugs)} markets")
        print("=" * 70)

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
                print(f"   ✅ {trade['question'][:50]}... | {trade['side']}")

        print(f"\n" + "=" * 70)
        print("💡 Start monitoring:")
        print("   ./scripts/bash/restart_monitor_autosell.sh")
        print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python buy_by_slug.py <slug1> <slug2> <slug3> ...")
        print()
        print("Example:")
        print("  python buy_by_slug.py fed-decision-in-october trump-wins-election")
        print()
        print("Get slug from Polymarket URL:")
        print("  https://polymarket.com/event/fed-decision-in-october")
        print("                              ↑")
        print("                          slug: fed-decision-in-october")
        sys.exit(1)

    slugs = sys.argv[1:]
    main(slugs, amount_per_trade=1.0)
