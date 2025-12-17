from agents.application.executor import Executor as Agent
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.polymarket.polymarket import Polymarket

import shutil
import json
import re


class Trader:
    def __init__(self):
        self.polymarket = Polymarket()
        self.gamma = Gamma()
        self.agent = Agent()

    def pre_trade_logic(self) -> None:
        self.clear_local_dbs()

    def clear_local_dbs(self) -> None:
        try:
            shutil.rmtree("local_db_events")
        except:
            pass
        try:
            shutil.rmtree("local_db_markets")
        except:
            pass

    def one_best_trade(self, mode: str = "rag") -> None:
        """
        one_best_trade is a strategy that evaluates all events, markets, and orderbooks
        leverages all available information sources accessible to the autonomous agent
        then executes that trade without any human intervention

        Args:
            mode: Trading mode
                - "simple": simplified mode, filter by liquidity
                - "rag": RAG-enhanced mode, AI semantic filtering + liquidity filtering (recommended)
                - "full": full mode, uses ChromaDB (may be unstable)
        """
        if mode == "simple":
            self._simple_trade()
        elif mode == "rag":
            self._rag_trade()
        else:
            self._full_trade()

    def _rag_trade(self) -> None:
        """RAG-enhanced trading: AI semantic filtering + liquidity filtering."""
        print("=" * 60)
        print("🚀 Auto trading agent - RAG enhanced mode")
        print("=" * 60)

        try:
            # 1. Fetch a large set of active markets
            print()
            print("📊 Step 1: Fetch active markets...")
            markets = self.gamma.get_all_current_markets(limit=500)
            print(f"   Found {len(markets)} active markets")

            # 2. Pre-filter by liquidity
            print()
            print("💧 Step 2: Liquidity pre-filter...")
            liquid_markets = []
            for m in markets:
                volume = float(m.get('volume', 0) or 0)
                liquidity = float(m.get('liquidity', 0) or 0)
                # Filter markets with enough liquidity
                if volume > 5000 or liquidity > 500:
                    liquid_markets.append(m)
            print(f"   After liquidity filter: {len(liquid_markets)} markets")

            if not liquid_markets:
                liquid_markets = markets[:20]  # Fallback: take top 20

            # 3. RAG semantic filtering - have the AI select markets most suitable to trade
            print()
            print("🤖 Step 3: AI semantic filtering (RAG)...")

            # Build market summaries for AI analysis
            market_summaries = []
            for i, m in enumerate(liquid_markets[:30]):  # Analyze up to 30
                q = m.get('question', '')
                prices = m.get('outcomePrices', [])
                if isinstance(prices, str):
                    prices = json.loads(prices)
                yes_price = float(prices[0]) if prices else 0.5
                market_summaries.append(f"{i+1}. {q} (Yes price: {yes_price:.1%})")

            # Ask AI to select the best markets to trade
            rag_prompt = f"""You are a professional prediction market trader. Here are the currently active prediction markets:

{chr(10).join(market_summaries)}

Select 1-3 markets you think are most suitable to trade (where you are most confident in your forecast).
Consider:
1. Your domain knowledge
2. Whether market pricing might be wrong
3. Recent related news/events

Reply with market numbers only, comma-separated. Example: 3,7,12"""

            from langchain_core.messages import HumanMessage
            result = self.agent.llm.invoke([HumanMessage(content=rag_prompt)])
            ai_selection = result.content
            print(f"   AI selection: {ai_selection}")

            # Parse market indices selected by AI
            import re
            selected_indices = re.findall(r'\d+', ai_selection)
            selected_indices = [int(i)-1 for i in selected_indices if int(i)-1 < len(liquid_markets)]

            if not selected_indices:
                selected_indices = [0]

            # 4. Deep analysis of selected markets
            print()
            print("🔬 Step 4: Deep analysis of selected markets...")

            best_trade = None
            best_edge = 0

            for idx in selected_indices[:3]:  # Analyze up to 3
                market = liquid_markets[idx]
                question = market.get('question', 'N/A')
                description = market.get('description', '')[:500]
                outcomes = market.get('outcomes', [])
                prices = market.get('outcomePrices', [])

                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if isinstance(prices, str):
                    prices = json.loads(prices)

                print(f"\n   Analyzing: {question}")

                # AI forecast
                prediction = self.agent.get_superforecast(
                    event_title=question,
                    market_question=question,
                    outcome=outcomes[0] if outcomes else "Yes"
                )

                # Extract probability (supports multiple formats)
                ai_prob = 0.5  # Default
                # Try matching "likelihood 0.35" or "likelihood `0.35`"
                prob_match = re.search(r'likelihood[^\d]*([0-9.]+)', prediction, re.IGNORECASE)
                if prob_match:
                    prob_value = float(prob_match.group(1))
                    # If value > 1, assume it is a percent
                    if prob_value > 1:
                        ai_prob = prob_value / 100
                    else:
                        ai_prob = prob_value
                    # Clamp to reasonable range
                    ai_prob = max(0.01, min(0.99, ai_prob))
                yes_price = float(prices[0]) if prices else 0.5

                edge = abs(ai_prob - yes_price)
                print(f"   Market price: {yes_price:.1%}, AI forecast: {ai_prob:.1%}, Edge: {edge:.1%}")

                if edge > best_edge:
                    best_edge = edge
                    best_trade = {
                        'market': market,
                        'question': question,
                        'outcomes': outcomes,
                        'prices': prices,
                        'ai_prob': ai_prob,
                        'yes_price': yes_price,
                        'edge': edge,
                        'prediction': prediction
                    }

            # 5. Final trading recommendation
            print()
            print("=" * 60)
            print("💡 Step 5: Final trading recommendation")
            print("=" * 60)

            if best_trade:
                print(f"\n   🎯 Best market: {best_trade['question']}")
                print(f"   📊 Market price: {best_trade['yes_price']:.1%}")
                print(f"   🤖 AI forecast: {best_trade['ai_prob']:.1%}")
                print(f"   📈 Edge: {best_trade['edge']:.1%}")

                if best_trade['ai_prob'] > best_trade['yes_price'] + 0.05:
                    side = "BUY"
                    target = best_trade['outcomes'][0] if best_trade['outcomes'] else "Yes"
                    print(f"\n   ✅ Recommendation: {side} {target}")
                elif best_trade['ai_prob'] < best_trade['yes_price'] - 0.05:
                    side = "BUY"
                    target = best_trade['outcomes'][1] if len(best_trade['outcomes']) > 1 else "No"
                    print(f"\n   ✅ Recommendation: {side} {target}")
                else:
                    print(f"\n   ⚖️ Recommendation: Wait (insufficient edge)")
                    side = None

                # Trade execution
                print()
                print("🎯 Step 6: Trade execution")
                print("   ⚠️ Currently in simulated mode - no real trade executed")

                usdc_balance = self.polymarket.get_usdc_balance()
                print(f"   Wallet balance: ${usdc_balance:.2f}")

                if side:
                    size = min(0.1, best_trade['edge'])
                    print(f"   Suggested position size: {size*100:.1f}%")
                    # Real trade (commented out)
                    # trade = self.polymarket.execute_market_order(best_trade['market'], usdc_balance * size)

            print()
            print("=" * 60)
            print("✅ RAG enhanced trading analysis complete!")
            print("=" * 60)

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    def _simple_trade(self) -> None:
        """Simplified trading: fetch markets from Gamma API and analyze."""
        print("=" * 60)
        print("🚀 Auto trading agent - simplified mode")
        print("=" * 60)

        try:
            # 1. Fetch active markets
            print()
            print("📊 Step 1: Fetch active markets...")
            markets = self.gamma.get_current_markets(limit=20)
            print(f"   Found {len(markets)} active markets")

            # 2. Select a market (with sufficient liquidity)
            print()
            print("🔍 Step 2: Select best market...")
            selected_market = None
            for m in markets:
                volume = m.get('volume', 0) or 0
                liquidity = m.get('liquidity', 0) or 0
                if float(volume) > 1000 or float(liquidity) > 100:
                    selected_market = m
                    break

            if not selected_market:
                selected_market = markets[0]

            question = selected_market.get('question', 'N/A')
            description = selected_market.get('description', '')[:300]
            outcomes = selected_market.get('outcomes', [])
            prices = selected_market.get('outcomePrices', [])

            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if isinstance(prices, str):
                prices = json.loads(prices)

            print(f"   Selected: {question}")
            print(f"   Outcomes: {outcomes}")
            print(f"   Prices: {prices}")

            # 3. AI superforecaster analysis
            print()
            print("🤖 Step 3: AI superforecaster analysis...")
            prediction = self.agent.get_superforecast(
                event_title=question,
                market_question=question,
                outcome=outcomes[0] if outcomes else "Yes"
            )
            print(f"   Prediction: {prediction}")

            # 4. Trading recommendation
            print()
            print("💡 Step 4: Trading recommendation...")

            yes_price = float(prices[0]) if prices and prices[0] else 0

            # Extract AI probability
            prob_match = re.search(r'likelihood.*?([0-9.]+)', prediction)
            ai_prob = float(prob_match.group(1)) if prob_match else 0.5

            print(f"   Current {outcomes[0] if outcomes else 'Yes'} price: ${yes_price:.3f} ({yes_price*100:.1f}%)")
            print(f"   AI forecast probability: {ai_prob*100:.1f}%")

            # Trade decision
            edge = ai_prob - yes_price
            if edge > 0.05:
                side = "BUY"
                target = outcomes[0] if outcomes else "Yes"
                size = min(0.1, edge)  # Position size based on edge
                print(f"   📈 Recommendation: {side} {target}")
                print(f"   Edge: +{edge*100:.1f}%")
                print(f"   Suggested position size: {size*100:.1f}% of capital")
            elif edge < -0.05:
                side = "BUY"
                target = outcomes[1] if len(outcomes) > 1 else "No"
                size = min(0.1, abs(edge))
                print(f"   📉 Recommendation: {side} {target}")
                print(f"   Edge: {edge*100:.1f}%")
                print(f"   Suggested position size: {size*100:.1f}% of capital")
            else:
                print(f"   ⚖️ Recommendation: Wait (insufficient edge)")
                side = None

            # 5. Simulate/execute trade
            print()
            print("🎯 Step 5: Trade execution")
            print("   ⚠️ Currently in simulated mode - no real trade executed")
            print("   For real trading, uncomment the relevant lines in trade.py")

            # Calculate trade amount
            usdc_balance = self.polymarket.get_usdc_balance()
            print(f"   Wallet balance: ${usdc_balance:.2f}")

            if side and usdc_balance > 0:
                trade_amount = usdc_balance * size
                print(f"   Simulated trade amount: ${trade_amount:.2f}")

                # Real trade (commented out)
                # Please refer to TOS before uncommenting: polymarket.com/tos
                # trade = self.polymarket.execute_market_order(selected_market, trade_amount)
                # print(f"   ✅ Trade executed: {trade}")

            print()
            print("=" * 60)
            print("✅ Auto trading analysis complete!")
            print("=" * 60)

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    def _full_trade(self) -> None:
        """Full trading mode: uses RAG filtering."""
        try:
            self.pre_trade_logic()

            events = self.polymarket.get_all_tradeable_events()
            print(f"1. FOUND {len(events)} EVENTS")

            filtered_events = self.agent.filter_events_with_rag(events)
            print(f"2. FILTERED {len(filtered_events)} EVENTS")

            markets = self.agent.map_filtered_events_to_markets(filtered_events)
            print()
            print(f"3. FOUND {len(markets)} MARKETS")

            print()
            filtered_markets = self.agent.filter_markets(markets)
            print(f"4. FILTERED {len(filtered_markets)} MARKETS")

            market = filtered_markets[0]
            best_trade = self.agent.source_best_trade(market)
            print(f"5. CALCULATED TRADE {best_trade}")

            amount = self.agent.format_trade_prompt_for_execution(best_trade)
            # Please refer to TOS before uncommenting: polymarket.com/tos
            # trade = self.polymarket.execute_market_order(market, amount)
            # print(f"6. TRADED {trade}")

        except Exception as e:
            print(f"Error {e} \n \n Retrying")
            self._full_trade()

    def maintain_positions(self):
        pass

    def incentive_farm(self):
        pass


if __name__ == "__main__":
    t = Trader()
    t.one_best_trade()
