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
            mode: 交易模式
                - "simple": 简化模式，按流动性筛选
                - "rag": RAG 增强模式，AI 语义筛选 + 流动性筛选（推荐）
                - "full": 完整模式，使用 ChromaDB（可能不稳定）
        """
        if mode == "simple":
            self._simple_trade()
        elif mode == "rag":
            self._rag_trade()
        else:
            self._full_trade()

    def _rag_trade(self) -> None:
        """RAG 增强交易模式：AI 语义筛选 + 流动性筛选"""
        print("=" * 60)
        print("🚀 自动交易代理 - RAG 增强模式")
        print("=" * 60)
        
        try:
            # 1. 获取大量活跃市场
            print()
            print("📊 Step 1: 获取活跃市场...")
            markets = self.gamma.get_all_current_markets(limit=100)
            print(f"   找到 {len(markets)} 个活跃市场")
            
            # 2. 流动性预筛选
            print()
            print("💧 Step 2: 流动性预筛选...")
            liquid_markets = []
            for m in markets:
                volume = float(m.get('volume', 0) or 0)
                liquidity = float(m.get('liquidity', 0) or 0)
                # 筛选有足够流动性的市场
                if volume > 5000 or liquidity > 500:
                    liquid_markets.append(m)
            print(f"   流动性筛选后: {len(liquid_markets)} 个市场")
            
            if not liquid_markets:
                liquid_markets = markets[:20]  # 保底取前20个
            
            # 3. RAG 语义筛选 - 让 AI 选择最适合交易的市场
            print()
            print("🤖 Step 3: AI 语义筛选（RAG）...")
            
            # 构建市场摘要供 AI 分析
            market_summaries = []
            for i, m in enumerate(liquid_markets[:30]):  # 最多分析30个
                q = m.get('question', '')
                prices = m.get('outcomePrices', [])
                if isinstance(prices, str):
                    prices = json.loads(prices)
                yes_price = float(prices[0]) if prices else 0.5
                market_summaries.append(f"{i+1}. {q} (Yes价格: {yes_price:.1%})")
            
            # 让 AI 选择最适合交易的市场
            rag_prompt = f"""你是一个专业的预测市场交易员。以下是当前活跃的预测市场：

{chr(10).join(market_summaries)}

请选择 1-3 个你认为最适合交易的市场（你最有把握预测准确的）。
考虑因素：
1. 你对该领域的了解程度
2. 市场定价是否可能有误
3. 近期是否有相关新闻或事件

请只回复市场编号，用逗号分隔。例如：3,7,12"""

            from langchain_core.messages import HumanMessage
            result = self.agent.llm.invoke([HumanMessage(content=rag_prompt)])
            ai_selection = result.content
            print(f"   AI 选择: {ai_selection}")
            
            # 解析 AI 选择的市场编号
            import re
            selected_indices = re.findall(r'\d+', ai_selection)
            selected_indices = [int(i)-1 for i in selected_indices if int(i)-1 < len(liquid_markets)]
            
            if not selected_indices:
                selected_indices = [0]
            
            # 4. 对选中的市场进行深度分析
            print()
            print("🔬 Step 4: 深度分析选中市场...")
            
            best_trade = None
            best_edge = 0
            
            for idx in selected_indices[:3]:  # 最多分析3个
                market = liquid_markets[idx]
                question = market.get('question', 'N/A')
                description = market.get('description', '')[:500]
                outcomes = market.get('outcomes', [])
                prices = market.get('outcomePrices', [])
                
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if isinstance(prices, str):
                    prices = json.loads(prices)
                
                print(f"\n   分析: {question}")
                
                # AI 预测
                prediction = self.agent.get_superforecast(
                    event_title=question,
                    market_question=question,
                    outcome=outcomes[0] if outcomes else "Yes"
                )
                
                # 提取概率（支持多种格式）
                ai_prob = 0.5  # 默认值
                # 尝试匹配 "likelihood 0.35" 或 "likelihood `0.35`"
                prob_match = re.search(r'likelihood[^\d]*([0-9.]+)', prediction, re.IGNORECASE)
                if prob_match:
                    prob_value = float(prob_match.group(1))
                    # 如果值大于1，假设是百分比格式
                    if prob_value > 1:
                        ai_prob = prob_value / 100
                    else:
                        ai_prob = prob_value
                    # 限制在合理范围内
                    ai_prob = max(0.01, min(0.99, ai_prob))
                yes_price = float(prices[0]) if prices else 0.5
                
                edge = abs(ai_prob - yes_price)
                print(f"   市场价格: {yes_price:.1%}, AI预测: {ai_prob:.1%}, 边际: {edge:.1%}")
                
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
            
            # 5. 生成最终交易建议
            print()
            print("=" * 60)
            print("💡 Step 5: 最终交易建议")
            print("=" * 60)
            
            if best_trade:
                print(f"\n   🎯 最佳市场: {best_trade['question']}")
                print(f"   📊 市场价格: {best_trade['yes_price']:.1%}")
                print(f"   🤖 AI 预测: {best_trade['ai_prob']:.1%}")
                print(f"   📈 边际: {best_trade['edge']:.1%}")
                
                if best_trade['ai_prob'] > best_trade['yes_price'] + 0.05:
                    side = "BUY"
                    target = best_trade['outcomes'][0] if best_trade['outcomes'] else "Yes"
                    print(f"\n   ✅ 建议: {side} {target}")
                elif best_trade['ai_prob'] < best_trade['yes_price'] - 0.05:
                    side = "BUY"
                    target = best_trade['outcomes'][1] if len(best_trade['outcomes']) > 1 else "No"
                    print(f"\n   ✅ 建议: {side} {target}")
                else:
                    print(f"\n   ⚖️ 建议: 观望 (边际不足)")
                    side = None
                
                # 交易执行
                print()
                print("🎯 Step 6: 交易执行")
                print("   ⚠️ 当前为模拟模式 - 不执行真实交易")
                
                usdc_balance = self.polymarket.get_usdc_balance()
                print(f"   钱包余额: ${usdc_balance:.2f}")
                
                if side:
                    size = min(0.1, best_trade['edge'])
                    print(f"   建议仓位: {size*100:.1f}%")
                    # 真实交易（已注释）
                    # trade = self.polymarket.execute_market_order(best_trade['market'], usdc_balance * size)
            
            print()
            print("=" * 60)
            print("✅ RAG 增强交易分析完成！")
            print("=" * 60)
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()

    def _simple_trade(self) -> None:
        """简化交易模式：直接从 Gamma API 获取市场并分析"""
        print("=" * 60)
        print("🚀 自动交易代理 - 简化模式")
        print("=" * 60)
        
        try:
            # 1. 获取活跃市场
            print()
            print("📊 Step 1: 获取活跃市场...")
            markets = self.gamma.get_current_markets(limit=20)
            print(f"   找到 {len(markets)} 个活跃市场")
            
            # 2. 选择一个市场（选择有足够流动性的）
            print()
            print("🔍 Step 2: 选择最佳市场...")
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
            
            print(f"   选中: {question}")
            print(f"   选项: {outcomes}")
            print(f"   价格: {prices}")
            
            # 3. AI 超级预测者分析
            print()
            print("🤖 Step 3: AI 超级预测者分析...")
            prediction = self.agent.get_superforecast(
                event_title=question,
                market_question=question,
                outcome=outcomes[0] if outcomes else "Yes"
            )
            print(f"   预测: {prediction}")
            
            # 4. 生成交易建议
            print()
            print("💡 Step 4: 生成交易建议...")
            
            yes_price = float(prices[0]) if prices and prices[0] else 0
            
            # 提取 AI 预测概率
            prob_match = re.search(r'likelihood.*?([0-9.]+)', prediction)
            ai_prob = float(prob_match.group(1)) if prob_match else 0.5
            
            print(f"   当前 {outcomes[0] if outcomes else 'Yes'} 价格: ${yes_price:.3f} ({yes_price*100:.1f}%)")
            print(f"   AI 预测概率: {ai_prob*100:.1f}%")
            
            # 交易决策
            edge = ai_prob - yes_price
            if edge > 0.05:
                side = "BUY"
                target = outcomes[0] if outcomes else "Yes"
                size = min(0.1, edge)  # 根据边际决定仓位
                print(f"   📈 建议: {side} {target}")
                print(f"   边际: +{edge*100:.1f}%")
                print(f"   建议仓位: {size*100:.1f}% 资金")
            elif edge < -0.05:
                side = "BUY"
                target = outcomes[1] if len(outcomes) > 1 else "No"
                size = min(0.1, abs(edge))
                print(f"   📉 建议: {side} {target}")
                print(f"   边际: {edge*100:.1f}%")
                print(f"   建议仓位: {size*100:.1f}% 资金")
            else:
                print(f"   ⚖️ 建议: 观望 (边际不足)")
                side = None
            
            # 5. 模拟/执行交易
            print()
            print("🎯 Step 5: 交易执行")
            print("   ⚠️ 当前为模拟模式 - 不执行真实交易")
            print("   如需真实交易，请取消 trade.py 中的注释")
            
            # 计算交易金额
            usdc_balance = self.polymarket.get_usdc_balance()
            print(f"   钱包余额: ${usdc_balance:.2f}")
            
            if side and usdc_balance > 0:
                trade_amount = usdc_balance * size
                print(f"   模拟交易金额: ${trade_amount:.2f}")
                
                # 真实交易（已注释）
                # Please refer to TOS before uncommenting: polymarket.com/tos
                # trade = self.polymarket.execute_market_order(selected_market, trade_amount)
                # print(f"   ✅ 交易执行: {trade}")
            
            print()
            print("=" * 60)
            print("✅ 自动交易分析完成！")
            print("=" * 60)
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()

    def _full_trade(self) -> None:
        """完整交易模式：使用 RAG 过滤"""
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
