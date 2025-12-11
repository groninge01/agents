"""
通过市场 Slug 精确购买
从 Polymarket 网页 URL 获取 slug，例如：
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
    """通过 slug 购买市场"""
    gamma = GammaMarketClient()
    
    # 获取市场数据
    try:
        # 尝试作为 event slug
        markets = gamma.get_event(slug)
        if not markets:
            # 尝试作为 market slug
            markets = [gamma.get_market(slug)]
    except:
        print(f"   ❌ 无法找到市场: {slug}")
        return None
    
    if not markets or not markets[0]:
        print(f"   ❌ 无法找到市场: {slug}")
        return None
    
    market = markets[0]
    question = market.get('question', '')
    
    print(f"   📋 {question[:50]}...")
    
    # AI 分析
    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        prices = json.loads(prices)
    yes_price = float(prices[0]) if prices else 0.5
    
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
    elif ai_prob < yes_price - 0.05:
        side = 'No'
    else:
        side = 'Yes' if ai_prob >= 0.5 else 'No'
    
    print(f"   AI预测: {ai_prob:.0%} | 市场: {yes_price:.0%} | 买入: {side}")
    
    # 获取 token_id
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
            buy_price = yes_price if side == 'Yes' else (1 - yes_price)
        
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
        
        print(f"   ✅ 买入成功!")
        
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
        print(f"   ❌ 错误: {e}")
        return None


def main(slugs, amount_per_trade=1.0):
    """主函数"""
    print("=" * 70)
    print("🎯 通过 Slug 精确购买")
    print("=" * 70)
    print(f"市场数量: {len(slugs)}")
    print(f"每笔金额: ${amount_per_trade}")
    print(f"总投资: ${len(slugs) * amount_per_trade}")
    print("=" * 70)
    
    # 初始化
    polymarket = Polymarket()
    executor = Executor()
    
    # 检查余额
    balance = polymarket.get_usdc_balance()
    print(f"\n💳 钱包余额: ${balance:.2f}")
    
    total_needed = len(slugs) * amount_per_trade
    if balance < total_needed:
        print(f"❌ 余额不足！需要 ${total_needed:.2f}")
        return
    
    # 购买
    print(f"\n🚀 开始购买...")
    print()
    
    successful_trades = []
    
    for i, slug in enumerate(slugs, 1):
        print(f"[{i}/{len(slugs)}] {slug}")
        trade = buy_market_by_slug(polymarket, executor, slug, amount_per_trade)
        
        if trade:
            successful_trades.append(trade)
        print()
    
    # 添加到监控
    if successful_trades:
        print("=" * 70)
        print(f"✅ 购买完成: {len(successful_trades)}/{len(slugs)} 个市场")
        print("=" * 70)
        
        pm = PositionManager()
        
        print(f"\n📋 添加到持仓监控...")
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
        print("💡 启动监控:")
        print("   ./scripts/bash/restart_monitor_autosell.sh")
        print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python buy_by_slug.py <slug1> <slug2> <slug3> ...")
        print()
        print("示例:")
        print("  python buy_by_slug.py fed-decision-in-october trump-wins-election")
        print()
        print("从 Polymarket URL 获取 slug:")
        print("  https://polymarket.com/event/fed-decision-in-october")
        print("                              ↑")
        print("                          slug: fed-decision-in-october")
        sys.exit(1)
    
    slugs = sys.argv[1:]
    main(slugs, amount_per_trade=1.0)




