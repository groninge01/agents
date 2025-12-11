"""
Solana Up or Down 市场购买脚本
每15分钟开盘一次，每秒轮询检查市场是否开盘
一旦开盘立即购买
"""

import json
import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

from agents.polymarket.gamma import GammaMarketClient
from agents.polymarket.polymarket import Polymarket
from scripts.python.position_monitor import PositionManager

load_dotenv()


def find_solana_market(gamma):
    """查找 Solana Up or Down 市场"""
    # 搜索关键词
    search_keywords = [
        "solana up or down",
        "solana up/down",
        "sol up or down",
        "sol up/down"
    ]
    
    # Slug 模式（用于匹配 URL 中的市场标识）
    slug_patterns = [
        "sol-updown-15m",  # 例如: sol-updown-15m-1764972900
        "sol-updown",
        "solana-updown"
    ]
    
    # 获取所有活跃市场
    markets = gamma.get_all_current_markets(limit=500)
    
    for market in markets:
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        slug = market.get('slug', '').lower()
        
        # 检查是否匹配 Solana Up or Down 市场
        text_to_check = f"{question} {description} {slug}"
        
        # 方法1: 通过关键词搜索
        for keyword in search_keywords:
            if keyword in text_to_check:
                # 检查市场是否活跃且可交易
                if (market.get('active', False) and 
                    not market.get('closed', False) and
                    market.get('enableOrderBook', False)):
                    return market
        
        # 方法2: 通过 slug 模式搜索（更精确）
        for pattern in slug_patterns:
            if pattern in slug:
                # 检查市场是否活跃且可交易
                if (market.get('active', False) and 
                    not market.get('closed', False) and
                    market.get('enableOrderBook', False)):
                    return market
    
    return None


def buy_solana_market(polymarket, market, amount=1.0, side='Yes', dry_run=False):
    """购买 Solana 市场"""
    try:
        question = market.get('question', '')
        print(f"📋 市场: {question[:60]}...")
        
        # 获取 token IDs
        token_ids = market.get('clobTokenIds', [])
        if isinstance(token_ids, str):
            token_ids = json.loads(token_ids)
        
        if not token_ids or len(token_ids) < 2:
            print(f"   ❌ 无法获取 token IDs")
            return None
        
        # Yes = token_ids[0], No = token_ids[1]
        token_idx = 0 if side == 'Yes' else 1
        token_id = token_ids[token_idx]
        
        # 获取当前价格
        orderbook = polymarket.client.get_order_book(token_id)
        if not orderbook or not orderbook.asks:
            print(f"   ❌ 无法获取订单簿（市场可能还未开盘）")
            return None
        
        # 买入用 Ask 价格（最低卖单）
        best_ask = min(orderbook.asks, key=lambda x: float(x.price))
        buy_price = float(best_ask.price)
        
        # 计算数量
        min_amount = max(amount, 1.05)  # 至少 $1.05
        quantity = min_amount / buy_price
        quantity = round(quantity, 2)
        
        print(f"   方向: {side}")
        print(f"   价格: ${buy_price:.4f}")
        print(f"   数量: {quantity:.2f}")
        print(f"   金额: ${min_amount:.2f}")
        
        if dry_run:
            print(f"   📋 模拟模式 - 未执行实际交易")
            return {
                'question': question,
                'side': side,
                'token_id': token_id,
                'buy_price': buy_price,
                'quantity': quantity,
                'cost': min_amount,
                'order_id': 'simulated'
            }
        
        # 执行限价单
        result = polymarket.execute_order(
            price=buy_price,
            size=quantity,
            side="BUY",
            token_id=token_id
        )
        
        # 提取订单 ID
        order_id = result.get('orderID', result.get('id', '')) if isinstance(result, dict) else str(result)
        
        print(f"   ✅ BUY {side} ${amount} 成功!")
        print(f"   订单ID: {order_id[:20]}..." if len(order_id) > 20 else f"   订单ID: {order_id}")
        
        return {
            'question': question,
            'side': side,
            'token_id': token_id,
            'buy_price': buy_price,
            'quantity': quantity,
            'cost': min_amount,
            'order_id': order_id
        }
        
    except Exception as e:
        print(f"   ❌ 购买失败: {e}")
        return None


def poll_and_buy_solana(gamma, polymarket, amount=1.0, side='Yes', dry_run=False, max_wait_minutes=15):
    """
    轮询检查 Solana 市场是否开盘，一旦开盘立即购买
    
    Args:
        gamma: GammaMarketClient 实例
        polymarket: Polymarket 实例
        amount: 购买金额
        side: 购买方向 ('Yes' 或 'No')
        dry_run: 是否模拟运行
        max_wait_minutes: 最大等待时间（分钟）
    """
    print("=" * 70)
    print("🔍 Solana Up or Down 市场轮询购买")
    print("=" * 70)
    print(f"💰 购买金额: ${amount}")
    print(f"📊 购买方向: {side}")
    print(f"🔒 模式: {'模拟运行' if dry_run else '⚠️ 真实交易'}")
    print(f"⏰ 最大等待时间: {max_wait_minutes} 分钟")
    print("=" * 70)
    
    start_time = datetime.now()
    max_wait_seconds = max_wait_minutes * 60
    check_count = 0
    
    while True:
        check_count += 1
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 检查是否超时
        if elapsed > max_wait_seconds:
            print(f"\n⏰ 超时！已等待 {max_wait_minutes} 分钟，未找到开盘的市场")
            return None
        
        # 查找市场
        print(f"\n[{check_count}] 检查 Solana 市场... (已等待 {elapsed:.0f} 秒)")
        market = find_solana_market(gamma)
        
        if market:
            # 检查市场是否可交易（有订单簿）
            token_ids = market.get('clobTokenIds', [])
            if isinstance(token_ids, str):
                token_ids = json.loads(token_ids)
            
            if token_ids and len(token_ids) >= 2:
                token_id = token_ids[0] if side == 'Yes' else token_ids[1]
                
                try:
                    # 尝试获取订单簿
                    orderbook = polymarket.client.get_order_book(token_id)
                    
                    if orderbook and orderbook.asks:
                        print(f"✅ 找到开盘的 Solana 市场！")
                        print(f"   问题: {market.get('question', '')[:60]}...")
                        
                        # 购买
                        result = buy_solana_market(polymarket, market, amount, side, dry_run)
                        
                        if result:
                            # 添加到持仓监控
                            if not dry_run:
                                print("\n📋 添加到持仓监控...")
                                pm = PositionManager()
                                pm.add_position(
                                    token_id=result['token_id'],
                                    market_question=result['question'],
                                    side=result['side'],
                                    buy_price=result['buy_price'],
                                    quantity=result['quantity'],
                                    cost=result['cost'],
                                    order_id=result['order_id']
                                )
                                print(f"   ✅ 已添加到持仓监控")
                            
                            return result
                        
                except Exception as e:
                    # 市场可能还未完全开盘，继续等待
                    pass
        
        # 等待 1 秒后再次检查
        time.sleep(1)


if __name__ == "__main__":
    import sys
    
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--execute':
        dry_run = False
    
    gamma = GammaMarketClient()
    polymarket = Polymarket()
    
    poll_and_buy_solana(
        gamma=gamma,
        polymarket=polymarket,
        amount=1.0,
        side='Yes',
        dry_run=dry_run,
        max_wait_minutes=15
    )

