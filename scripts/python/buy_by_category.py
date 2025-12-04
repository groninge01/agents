"""
按类别购买市场
支持按 tags 筛选市场进行购买
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
    """用 AI 按类别筛选市场"""
    markets = gamma.get_all_current_markets(limit=200)
    
    # 预筛选：流动性和价格
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
    
    print(f"   预筛选: {len(candidates)} 个高流动性市场")
    
    # 按流动性排序，取前 50 个
    candidates.sort(key=lambda x: x['liquidity'], reverse=True)
    candidates = candidates[:50]
    
    # AI 分类
    results = {cat: [] for cat in categories}
    
    print(f"\n🤖 AI 分类市场...")
    
    # 构建市场列表
    market_list = [f"{i+1}. {m['question']}" for i, m in enumerate(candidates)]
    
    prompt = f'''你是市场分类专家。以下是预测市场列表：

{chr(10).join(market_list[:30])}  # 最多30个

请将这些市场分类到: {', '.join(categories)}

返回格式（每行一个）:
<类别>: <市场编号>,<市场编号>,...

例如:
finance: 1,3,5
culture: 2,7,9'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    response = result.content
    
    print("AI 分类结果:")
    print(response)
    print()
    
    # 解析 AI 分类结果
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
    """AI 从类别中选择市场"""
    if not candidates:
        return []
    
    market_list = []
    for i, m in enumerate(candidates[:20], 1):  # 最多显示20个
        market_list.append(f"{i}. {m['question']} (Yes:{m['yes_price']:.0%}, 流动性:\${m['liquidity']/1000:.0f}k)")
    
    prompt = f'''你是专业的 {category} 领域预测专家。以下是 {category} 类别的市场：

{chr(10).join(market_list)}

请选择 {count} 个你最有把握预测的市场。
只返回市场编号，用逗号分隔。例如：1,3,5'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    selection = result.content
    
    # 解析选择
    indices = re.findall(r'\d+', selection)
    indices = [int(i)-1 for i in indices if int(i)-1 < len(candidates)][:count]
    
    return [candidates[i] for i in indices]


def analyze_and_trade(executor, polymarket, market_info, amount):
    """分析并交易单个市场"""
    question = market_info['question']
    yes_price = market_info['yes_price']
    
    # AI 预测
    prompt = f'''分析: {question}
当前 Yes 价格: {yes_price:.0%}

你认为 Yes 的真实概率是多少？只返回数字（0-1），例如：0.65'''
    
    result = executor.llm.invoke([HumanMessage(content=prompt)])
    
    # 解析概率
    try:
        ai_prob = float(re.search(r'0?\.\d+', result.content).group())
    except:
        ai_prob = 0.5
    
    # 决定买入方向
    if ai_prob > yes_price + 0.05:
        side = 'Yes'
        edge = ai_prob - yes_price
    elif ai_prob < yes_price - 0.05:
        side = 'No'
        edge = yes_price - ai_prob
    else:
        side = 'Yes' if ai_prob >= 0.5 else 'No'
        edge = abs(ai_prob - yes_price)
    
    print(f"   AI预测: {ai_prob:.0%} | 买入: {side} | 边际: {edge:.0%}")
    
    # 获取 token_id
    market = market_info['market']
    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        token_ids = json.loads(token_ids)
    
    token_idx = 0 if side == 'Yes' else 1
    token_id = token_ids[token_idx] if token_ids else None
    
    if not token_id:
        print(f"   ❌ 无法获取 token_id")
        return None
    
    # 获取价格
    try:
        orderbook = polymarket.client.get_order_book(token_id)
        if orderbook and orderbook.asks:
            best_ask = min(orderbook.asks, key=lambda x: float(x.price))
            buy_price = float(best_ask.price)
        else:
            print(f"   ❌ 无法获取订单簿")
            return None
        
        # 计算数量
        min_amount = max(amount, 1.05)
        quantity = min_amount / buy_price
        quantity = round(quantity, 2)
        
        print(f"   价格: ${buy_price:.4f} | 数量: {quantity:.2f}")
        
        # 执行买单
        result = polymarket.execute_order(
            price=buy_price,
            size=quantity,
            side="BUY",
            token_id=token_id
        )
        
        order_id = result.get('orderID', result.get('id', '')) if isinstance(result, dict) else str(result)
        
        print(f"   ✅ 买入成功! 订单: {order_id[:20]}...")
        
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
        print(f"   ❌ 错误: {e}")
        return None


def main(categories=['finance', 'culture'], count_per_category=3, amount_per_trade=1.0):
    """主函数"""
    print("=" * 70)
    print("🎯 按类别购买市场")
    print("=" * 70)
    print(f"类别: {', '.join(categories)}")
    print(f"每类市场数: {count_per_category}")
    print(f"每笔金额: ${amount_per_trade}")
    print(f"总投资: ${len(categories) * count_per_category * amount_per_trade}")
    print("=" * 70)
    
    # 初始化
    gamma = GammaMarketClient()
    polymarket = Polymarket()
    executor = Executor()
    
    # 检查余额
    balance = polymarket.get_usdc_balance()
    print(f"\n💳 钱包余额: ${balance:.2f}")
    
    total_needed = len(categories) * count_per_category * amount_per_trade
    if balance < total_needed:
        print(f"❌ 余额不足！需要 ${total_needed:.2f}")
        return
    
    # 查找市场
    print(f"\n📊 查找市场...")
    category_markets = find_markets_by_category(gamma, executor, categories, count_per_category=count_per_category)
    
    for cat, markets in category_markets.items():
        print(f"   {cat}: 找到 {len(markets)} 个")
    
    # AI 选择
    print(f"\n🤖 AI 选择最佳市场...")
    selected_markets = {}
    
    for cat in categories:
        if category_markets[cat]:
            selected = ai_select_from_category(executor, category_markets[cat], cat, count_per_category)
            selected_markets[cat] = selected
            print(f"   {cat}: 选择 {len(selected)} 个")
        else:
            print(f"   ⚠️ {cat}: 没有找到符合条件的市场")
            selected_markets[cat] = []
    
    # 交易
    print(f"\n" + "=" * 70)
    print("🚀 开始交易")
    print("=" * 70)
    
    successful_trades = []
    
    for cat in categories:
        if not selected_markets[cat]:
            continue
            
        print(f"\n📁 {cat.upper()} 类别:")
        print("-" * 70)
        
        for i, market_info in enumerate(selected_markets[cat], 1):
            print(f"\n[{i}/{len(selected_markets[cat])}] {market_info['question'][:50]}...")
            trade = analyze_and_trade(executor, polymarket, market_info, amount_per_trade)
            
            if trade:
                successful_trades.append(trade)
    
    # 添加到监控
    if successful_trades:
        print(f"\n" + "=" * 70)
        print(f"✅ 购买完成: {len(successful_trades)} 个市场")
        print("=" * 70)
        
        from scripts.python.position_monitor import PositionManager
        pm = PositionManager()
        
        print(f"\n📋 添加到持仓监控...")
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
            print(f"   ✅ {trade['question'][:40]}... | {trade['side']}")
        
        print(f"\n" + "=" * 70)
        print("💡 启动监控:")
        print("   ./scripts/bash/restart_monitor_autosell.sh")
        print("=" * 70)
    else:
        print("\n❌ 没有成功的交易")


if __name__ == "__main__":
    import sys
    
    # 默认参数
    categories = ['finance', 'culture']
    count = 3
    amount = 1.0
    
    # 简单参数解析
    if len(sys.argv) > 1:
        # 支持: python buy_by_category.py finance culture 3 1.0
        if len(sys.argv) >= 3:
            categories = sys.argv[1].split(',')
        if len(sys.argv) >= 4:
            count = int(sys.argv[2])
        if len(sys.argv) >= 5:
            amount = float(sys.argv[3])
    
    main(categories=categories, count_per_category=count, amount_per_trade=amount)

