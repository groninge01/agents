"""
批量交易脚本 - 执行 10 个短期市场交易
每个市场投资 $1，总计 $10
"""

import json
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from agents.polymarket.gamma import GammaMarketClient

load_dotenv()
from agents.polymarket.polymarket import Polymarket
from agents.application.executor import Executor
from langchain_core.messages import HumanMessage


def find_short_term_markets(gamma, hours=48, min_liquidity=1000, count=30):
    """查找短期内结束的市场"""
    markets = gamma.get_all_current_markets(limit=500)
    now = datetime.utcnow()
    deadline = now + timedelta(hours=hours)
    
    short_term = []
    for m in markets:
        end_date_str = m.get('endDate', '')
        if not end_date_str:
            continue
        
        try:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).replace(tzinfo=None)
            
            if now < end_date <= deadline:
                liquidity = float(m.get('liquidity', 0) or 0)
                prices = m.get('outcomePrices', [])
                if isinstance(prices, str):
                    prices = json.loads(prices)
                
                yes_price = float(prices[0]) if prices else 0.5
                
                # 流动性足够且价格合理
                if liquidity > min_liquidity and 0.1 <= yes_price <= 0.9:
                    short_term.append({
                        'question': m.get('question', ''),
                        'end_date': end_date,
                        'hours_left': (end_date - now).total_seconds() / 3600,
                        'liquidity': liquidity,
                        'yes_price': yes_price,
                        'prices': prices,
                        'market': m
                    })
        except:
            continue
    
    # 按流动性排序
    short_term.sort(key=lambda x: x['liquidity'], reverse=True)
    return short_term[:count]


def ai_select_markets(executor, candidates, count=10):
    """让 AI 选择最有把握的市场"""
    market_list = []
    for i, m in enumerate(candidates, 1):
        market_list.append(f"{i}. {m['question']} (Yes:{m['yes_price']:.0%}, {m['hours_left']:.0f}h后结束)")
    
    selection_prompt = f'''你是一个专业的体育/政治预测专家。以下是即将结束的预测市场：

{chr(10).join(market_list)}

请选择 {count} 个你最有把握预测的市场。
只返回市场编号，用逗号分隔。例如：1,3,5,7,9,11,13,15,17,19'''

    result = executor.llm.invoke([HumanMessage(content=selection_prompt)])
    ai_selection = result.content
    
    # 解析选择
    selected_indices = re.findall(r'\d+', ai_selection)
    selected_indices = [int(i)-1 for i in selected_indices if int(i)-1 < len(candidates)][:count]
    
    # 补充到指定数量
    while len(selected_indices) < count and len(selected_indices) < len(candidates):
        for i in range(len(candidates)):
            if i not in selected_indices:
                selected_indices.append(i)
                if len(selected_indices) >= count:
                    break
    
    return selected_indices, ai_selection


def analyze_and_decide(executor, market):
    """分析市场并决定交易方向"""
    question = market['question']
    yes_price = market['yes_price']
    
    # AI 预测
    prediction = executor.get_superforecast(
        event_title=question,
        market_question=question,
        outcome='Yes'
    )
    
    # 提取概率
    ai_prob = 0.5
    prob_match = re.search(r'likelihood[^\d]*([0-9.]+)', prediction, re.IGNORECASE)
    if prob_match:
        prob_value = float(prob_match.group(1))
        if prob_value > 1:
            ai_prob = prob_value / 100
        else:
            ai_prob = prob_value
        ai_prob = max(0.05, min(0.95, ai_prob))
    
    # 决定买 Yes 还是 No
    if ai_prob > yes_price + 0.03:
        side = 'Yes'
        edge = ai_prob - yes_price
    elif ai_prob < yes_price - 0.03:
        side = 'No'
        edge = yes_price - ai_prob
    else:
        side = 'Yes' if ai_prob >= 0.5 else 'No'
        edge = abs(ai_prob - yes_price)
    
    return {
        'side': side,
        'ai_prob': ai_prob,
        'edge': edge,
        'prediction': prediction
    }


def execute_batch_trades(dry_run=True, amount_per_trade=1.0, num_trades=10):
    """执行批量交易"""
    
    print("=" * 70)
    print("🚀 批量交易脚本")
    print("=" * 70)
    print(f"💰 每笔交易金额: ${amount_per_trade}")
    print(f"📊 交易数量: {num_trades}")
    print(f"💵 总投资: ${amount_per_trade * num_trades}")
    print(f"🔒 模式: {'模拟运行' if dry_run else '⚠️ 真实交易'}")
    print("=" * 70)
    
    # 初始化
    gamma = GammaMarketClient()
    polymarket = Polymarket()
    executor = Executor()
    
    # 检查余额
    usdc_balance = polymarket.get_usdc_balance()
    print(f"\n💳 钱包余额: ${usdc_balance:.2f}")
    
    total_needed = amount_per_trade * num_trades
    if usdc_balance < total_needed:
        print(f"❌ 余额不足！需要 ${total_needed}，只有 ${usdc_balance:.2f}")
        return
    
    # 1. 查找短期市场
    print("\n📊 Step 1: 查找 48 小时内结束的市场...")
    candidates = find_short_term_markets(gamma, hours=48)
    print(f"   找到 {len(candidates)} 个符合条件的市场")
    
    # 2. AI 选择
    print("\n🤖 Step 2: AI 选择最佳市场...")
    selected_indices, ai_selection = ai_select_markets(executor, candidates, num_trades)
    print(f"   AI 选择: {ai_selection}")
    
    # 3. 分析并生成交易计划
    print("\n🔬 Step 3: 分析选中的市场...")
    trade_plan = []
    
    for idx in selected_indices:
        m = candidates[idx]
        print(f"\n   分析: {m['question'][:50]}...")
        
        decision = analyze_and_decide(executor, m)
        
        trade_plan.append({
            'question': m['question'],
            'market': m['market'],
            'hours_left': m['hours_left'],
            **decision
        })
        
        print(f"   -> BUY {decision['side']} | AI: {decision['ai_prob']:.0%} | 边际: {decision['edge']:.0%}")
    
    # 4. 显示交易计划
    print("\n" + "=" * 70)
    print("📋 交易计划")
    print("=" * 70)
    
    for i, t in enumerate(trade_plan, 1):
        q = t['question'][:45] + '...' if len(t['question']) > 48 else t['question']
        print(f"{i:2}. {q}")
        print(f"    BUY {t['side']} | AI预测: {t['ai_prob']:.0%} | 边际: {t['edge']:.0%} | {t['hours_left']:.0f}h后结束")
    
    # 5. 执行交易
    print("\n" + "=" * 70)
    if dry_run:
        print("🔒 模拟运行完成 - 未执行真实交易")
        print("=" * 70)
        print("\n要执行真实交易，请运行:")
        print("  python scripts/python/batch_trade.py --execute")
        return trade_plan
    else:
        print("⚠️ 即将执行真实交易...")
        print("=" * 70)
        
        print("\n🚀 开始执行交易...")
        
        successful_trades = []
        for i, t in enumerate(trade_plan, 1):
            print(f"\n交易 {i}/{len(trade_plan)}: {t['question'][:40]}...")
            try:
                # 获取 token_id
                market = t['market']
                token_ids = market.get('clobTokenIds', [])
                if isinstance(token_ids, str):
                    token_ids = json.loads(token_ids)
                
                # Yes = token_ids[0], No = token_ids[1]
                token_idx = 0 if t['side'] == 'Yes' else 1
                token_id = token_ids[token_idx] if token_ids else None
                
                if not token_id:
                    print(f"   ❌ 无法获取 token_id")
                    continue
                
                # 获取当前价格
                orderbook = polymarket.client.get_order_book(token_id)
                if orderbook and orderbook.asks:
                    # 买入用 Ask 价格（最低卖单）
                    best_ask = min(orderbook.asks, key=lambda x: float(x.price))
                    buy_price = float(best_ask.price)
                else:
                    print(f"   ❌ 无法获取订单簿")
                    continue
                
                # 计算数量 (确保金额 >= $1.01 以避免精度问题)
                min_amount = max(amount_per_trade, 1.05)  # 至少 $1.05
                quantity = min_amount / buy_price
                quantity = round(quantity, 2)  # 保留2位小数
                
                print(f"   价格: ${buy_price:.4f}")
                print(f"   数量: {quantity:.2f}")
                
                # 执行限价单
                result = polymarket.execute_order(
                    price=buy_price,
                    size=quantity,
                    side="BUY",
                    token_id=token_id
                )
                
                # 提取订单 ID
                order_id = result.get('orderID', result.get('id', '')) if isinstance(result, dict) else str(result)
                
                print(f"   ✅ BUY {t['side']} ${amount_per_trade} 成功!")
                print(f"   订单ID: {order_id[:20]}..." if len(order_id) > 20 else f"   订单ID: {order_id}")
                
                # 记录成功的交易
                actual_cost = buy_price * quantity  # 实际成本 = 价格 × 数量
                successful_trades.append({
                    'question': t['question'],
                    'side': t['side'],
                    'token_id': token_id,
                    'buy_price': buy_price,
                    'quantity': quantity,
                    'cost': actual_cost,
                    'ai_prob': t['ai_prob'],
                    'order_id': order_id
                })
                    
            except Exception as e:
                print(f"   ❌ 错误: {e}")
        
        # 将成功的交易添加到持仓监控
        if successful_trades:
            print("\n📋 添加到持仓监控...")
            from scripts.python.position_monitor import PositionManager
            pm = PositionManager()
            for trade in successful_trades:
                pm.add_position(
                    token_id=trade['token_id'],
                    market_question=trade['question'],
                    side=trade['side'],
                    buy_price=trade['buy_price'],
                    quantity=trade['quantity'],
                    cost=trade['cost'],
                    order_id=trade.get('order_id', '')
                )
                print(f"   ✅ 已添加: {trade['question'][:40]}...")
        
        print("\n" + "=" * 70)
        print("✅ 批量交易完成！")
        print("=" * 70)


if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--execute':
        dry_run = False
    
    execute_batch_trades(
        dry_run=dry_run,
        amount_per_trade=1.0,
        num_trades=10
    )

