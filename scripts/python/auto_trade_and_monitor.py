"""
Auto trading + take-profit/stop-loss monitoring
1. Auto-select and buy a specified number of markets
2. Add them to position monitoring
3. Start take-profit/stop-loss monitoring
"""

import json
import re
from datetime import datetime
from agents.polymarket.gamma import GammaMarketClient
from agents.polymarket.polymarket import Polymarket
from agents.application.executor import Executor
from langchain_core.messages import HumanMessage
from scripts.python.position_monitor import PositionManager, TAKE_PROFIT_PCT, STOP_LOSS_PCT, MONITOR_INTERVAL, AUTO_EXECUTE


# ============================================================
# 📋 Trading configuration - edit here
# ============================================================

NUM_TRADES = 3              # Number of markets to buy
AMOUNT_PER_TRADE = 1.0      # Amount per market (USDC)
MIN_LIQUIDITY = 5000        # Minimum liquidity requirement
EXECUTE_TRADES = True       # Whether to execute real trades (False = simulate only)

# ============================================================


def select_best_markets(gamma, executor, num_markets=3):
    """AI selects the best markets."""
    print("\n📊 Fetching active markets...")
    markets = gamma.get_all_current_markets(limit=300)

    # Filter high-liquidity markets
    candidates = []
    for m in markets:
        liquidity = float(m.get('liquidity', 0) or 0)
        prices = m.get('outcomePrices', [])
        if isinstance(prices, str):
            prices = json.loads(prices)

        yes_price = float(prices[0]) if prices else 0.5

        # Enough liquidity and reasonable price
        if liquidity > MIN_LIQUIDITY and 0.15 <= yes_price <= 0.85:
            candidates.append({
                'question': m.get('question', ''),
                'liquidity': liquidity,
                'yes_price': yes_price,
                'market': m
            })

    # Sort by liquidity
    candidates.sort(key=lambda x: x['liquidity'], reverse=True)
    candidates = candidates[:30]  # Take top 30

    print(f"   Found {len(candidates)} candidate markets")

    # AI selection
    print("\n🤖 AI is selecting the best markets...")
    market_list = []
    for i, m in enumerate(candidates, 1):
        market_list.append(f"{i}. {m['question']} (Yes: {m['yes_price']:.0%}, Liquidity: ${m['liquidity']/1000:.0f}k)")

    prompt = f'''You are a professional prediction market trader. Here are active markets:

{chr(10).join(market_list)}

Select {num_markets} markets you are most confident forecasting.
Prefer: politics, tech, economics (rather than pure sports betting)
Reply with market numbers only, comma-separated. Example: 1,5,12'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    selection = result.content
    print(f"   AI selection: {selection}")

    # Parse selection
    indices = re.findall(r'\d+', selection)
    indices = [int(i)-1 for i in indices if int(i)-1 < len(candidates)][:num_markets]

    return [candidates[i] for i in indices]


def analyze_market(executor, market_info):
    """AI analyzes a single market."""
    prompt = f'''Analyze this prediction market:

Question: {market_info['question']}
Current Yes price: {market_info['yes_price']:.0%}

What do you think the true probability of Yes is?
Reply with a single number between 0 and 1, e.g. 0.65'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])

    # Parse probability
    try:
        prob = float(re.search(r'0?\.\d+', result.content).group())
    except:
        prob = 0.5

    # Decide buy side
    yes_price = market_info['yes_price']
    no_price = 1 - yes_price

    yes_edge = prob - yes_price
    no_edge = (1 - prob) - no_price

    if yes_edge > no_edge:
        return {'side': 'Yes', 'ai_prob': prob, 'buy_price': yes_price, 'edge': yes_edge}
    else:
        return {'side': 'No', 'ai_prob': 1 - prob, 'buy_price': no_price, 'edge': no_edge}


def execute_trade(polymarket, market_info, decision, amount):
    """Execute trade."""
    market = market_info['market']
    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        token_ids = json.loads(token_ids)

    # Yes = token 0, No = token 1
    token_index = 0 if decision['side'] == 'Yes' else 1
    token_id = token_ids[token_index] if token_ids else None

    if not token_id:
        return None, None

    # Calculate quantity (shares = amount / price)
    quantity = amount / decision['buy_price']

    if not EXECUTE_TRADES:
        print(f"   📋 Simulated trade: BUY {decision['side']} @ ${decision['buy_price']:.2f} x {quantity:.2f} shares")
        return token_id, quantity

    # Real trade
    try:
        result = polymarket.execute_order(
            price=decision['buy_price'],
            size=quantity,
            side="BUY",
            token_id=token_id
        )
        print(f"   ✅ Trade successful: {result}")
        return token_id, quantity
    except Exception as e:
        print(f"   ❌ Trade failed: {e}")
        return None, None


def main():
    print("=" * 70)
    print("🚀 Auto trade + take-profit/stop-loss monitoring")
    print("=" * 70)

    # Show configuration
    print(f"\n📋 Configuration:")
    print(f"   Trades: {NUM_TRADES} markets")
    print(f"   Amount per trade: ${AMOUNT_PER_TRADE}")
    print(f"   Total investment: ${NUM_TRADES * AMOUNT_PER_TRADE}")
    print(f"   Take-profit: {TAKE_PROFIT_PCT*100:.0f}%")
    print(f"   Stop-loss: {STOP_LOSS_PCT*100:.0f}%")
    print(f"   Monitor interval: {MONITOR_INTERVAL} seconds")
    print(f"   Execute trades: {'✅ Yes' if EXECUTE_TRADES else '❌ No (simulated)'}")

    # Init
    gamma = GammaMarketClient()
    polymarket = Polymarket()
    executor = Executor()
    pm = PositionManager()

    # Check balance
    print(f"\n💳 Checking balance...")
    try:
        balance = polymarket.get_usdc_balance()
        print(f"   USDC balance: ${balance:.2f}")

        total_needed = NUM_TRADES * AMOUNT_PER_TRADE
        if balance < total_needed and EXECUTE_TRADES:
            print(f"   ⚠️ Insufficient balance! Need ${total_needed:.2f}")
            return
    except Exception as e:
        print(f"   ⚠️ Unable to fetch balance: {e}")

    # Select markets
    selected = select_best_markets(gamma, executor, NUM_TRADES)

    if len(selected) < NUM_TRADES:
        print(f"\n⚠️ Only found {len(selected)} markets")

    # Analyze and trade
    print("\n" + "=" * 70)
    print("📈 Starting trades")
    print("=" * 70)

    successful_trades = []

    for i, market_info in enumerate(selected, 1):
        print(f"\n[{i}/{len(selected)}] {market_info['question'][:50]}...")

        # AI analysis
        decision = analyze_market(executor, market_info)
        print(f"   AI forecast: {decision['ai_prob']:.0%} | Buy: {decision['side']} @ ${decision['buy_price']:.2f}")

        # Execute trade
        token_id, quantity = execute_trade(polymarket, market_info, decision, AMOUNT_PER_TRADE)

        if token_id:
            # Add to position monitor
            position, is_new = pm.add_position(
                token_id=token_id,
                market_question=market_info['question'],
                side=decision['side'],
                buy_price=decision['buy_price'],
                quantity=quantity,
                cost=AMOUNT_PER_TRADE,
            )
            successful_trades.append({
                'question': market_info['question'],
                'side': decision['side'],
                'price': decision['buy_price'],
                'quantity': quantity
            })

    # Show results
    print("\n" + "=" * 70)
    print(f"✅ Completed {len(successful_trades)}/{len(selected)} trades")
    print("=" * 70)

    for i, t in enumerate(successful_trades, 1):
        print(f"   {i}. {t['question'][:40]}... | {t['side']} @ ${t['price']:.2f}")

    # Display positions
    pm.display_positions()

    # Start monitoring
    if successful_trades:
        print("\n" + "=" * 70)
        print("🔄 Starting take-profit/stop-loss monitoring")
        print("=" * 70)
        pm.monitor_loop()


if __name__ == "__main__":
    main()
