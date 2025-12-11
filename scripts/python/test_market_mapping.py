"""
测试市场映射工具
用于验证 Seahawks vs. Falcons 等市场的 Yes/No 映射是否正确
"""

import sys
import os

# 添加项目根目录到 Python 路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

from agents.polymarket.gamma import GammaMarketClient
from scripts.python.market_utils import get_market_info, get_price_for_side, get_token_id_for_side


def find_seahawks_falcons_market():
    """查找 Seahawks vs. Falcons 市场"""
    gamma = GammaMarketClient()
    markets = gamma.get_all_current_markets(limit=500)
    
    for market in markets:
        question = market.get('question', '').lower()
        if 'seahawks' in question and 'falcons' in question:
            return market
    
    return None


def test_market_mapping():
    """测试市场映射"""
    print("=" * 70)
    print("🔍 测试市场映射工具")
    print("=" * 70)
    
    # 查找 Seahawks vs. Falcons 市场
    print("\n查找 Seahawks vs. Falcons 市场...")
    market = find_seahawks_falcons_market()
    
    if not market:
        print("❌ 未找到 Seahawks vs. Falcons 市场")
        print("尝试查找其他体育比赛市场...")
        
        # 查找任意体育比赛市场
        gamma = GammaMarketClient()
        markets = gamma.get_all_current_markets(limit=100)
        
        sports_keywords = ['win', 'vs', 'beat', 'defeat', 'game', 'match']
        for m in markets:
            question = m.get('question', '').lower()
            if any(keyword in question for keyword in sports_keywords):
                market = m
                print(f"找到市场: {m.get('question', '')[:60]}...")
                break
        
        if not market:
            print("❌ 未找到合适的测试市场")
            return
    
    print(f"✅ 找到市场: {market.get('question', '')}")
    print()
    
    # 获取原始数据
    outcomes = market.get('outcome', []) or market.get('outcomes', [])
    if isinstance(outcomes, str):
        import json
        try:
            outcomes = json.loads(outcomes)
        except:
            outcomes = []
    
    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        import json
        try:
            prices = json.loads(prices)
        except:
            prices = []
    
    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        import json
        try:
            token_ids = json.loads(token_ids)
        except:
            token_ids = []
    
    print("原始数据:")
    print(f"  Outcomes: {outcomes}")
    print(f"  Prices: {prices}")
    print(f"  Token IDs: {token_ids}")
    print()
    
    # 使用工具函数获取映射信息
    market_info = get_market_info(market)
    
    print("映射结果:")
    print(f"  Yes 对应: {market_info['yes_outcome']} (价格: {market_info['yes_price']:.4f}, Token: {market_info['yes_token_id']})")
    print(f"  No 对应:  {market_info['no_outcome']} (价格: {market_info['no_price']:.4f}, Token: {market_info['no_token_id']})")
    print(f"  映射索引: {market_info['mapping']}")
    print()
    
    # 验证映射是否正确
    print("验证:")
    yes_price_direct = get_price_for_side(market, 'Yes')
    no_price_direct = get_price_for_side(market, 'No')
    yes_token_direct = get_token_id_for_side(market, 'Yes')
    no_token_direct = get_token_id_for_side(market, 'No')
    
    print(f"  get_price_for_side(market, 'Yes'): {yes_price_direct}")
    print(f"  get_price_for_side(market, 'No'): {no_price_direct}")
    print(f"  get_token_id_for_side(market, 'Yes'): {yes_token_direct}")
    print(f"  get_token_id_for_side(market, 'No'): {no_token_direct}")
    print()
    
    # 检查价格是否合理（应该加起来约等于 1）
    total_price = (yes_price_direct or 0) + (no_price_direct or 0)
    print(f"  价格总和: {total_price:.4f} (应该接近 1.0)")
    
    if abs(total_price - 1.0) > 0.1:
        print("  ⚠️ 警告: 价格总和偏离 1.0 较大，可能映射有误")
    else:
        print("  ✅ 价格总和合理")
    
    print("=" * 70)


if __name__ == "__main__":
    test_market_mapping()





