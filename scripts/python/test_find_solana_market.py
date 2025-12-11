"""
测试脚本：查找 Solana Up or Down 市场
测试是否能找到用户提供的市场：sol-updown-15m-1764972900
"""

import json
import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, PROJECT_ROOT)

from agents.polymarket.gamma import GammaMarketClient

load_dotenv()


def find_solana_market_by_slug_pattern(gamma, slug_pattern="sol-updown-15m"):
    """通过 slug 模式查找 Solana 市场"""
    print(f"🔍 搜索包含 '{slug_pattern}' 的市场...")
    
    # 获取所有活跃市场
    markets = gamma.get_all_current_markets(limit=500)
    print(f"   找到 {len(markets)} 个活跃市场")
    
    matches = []
    for market in markets:
        slug = market.get('slug', '').lower()
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        
        # 检查 slug 或问题中是否包含模式
        if (slug_pattern.lower() in slug or 
            slug_pattern.lower() in question or
            'solana up or down' in question or
            'sol up or down' in question):
            
            matches.append({
                'id': market.get('id'),
                'slug': market.get('slug'),
                'question': market.get('question'),
                'active': market.get('active'),
                'closed': market.get('closed'),
                'enableOrderBook': market.get('enableOrderBook'),
                'clobTokenIds': market.get('clobTokenIds'),
                'description': market.get('description', '')[:100]
            })
    
    return matches


def find_solana_market_by_keywords(gamma):
    """通过关键词查找 Solana 市场（使用现有逻辑）"""
    print(f"🔍 使用关键词搜索 Solana Up or Down 市场...")
    
    search_keywords = [
        "solana up or down",
        "solana up/down",
        "sol up or down",
        "sol up/down"
    ]
    
    markets = gamma.get_all_current_markets(limit=500)
    print(f"   找到 {len(markets)} 个活跃市场")
    
    matches = []
    for market in markets:
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        slug = market.get('slug', '').lower()
        
        text_to_check = f"{question} {description} {slug}"
        
        for keyword in search_keywords:
            if keyword in text_to_check:
                if (market.get('active', False) and 
                    not market.get('closed', False) and
                    market.get('enableOrderBook', False)):
                    
                    matches.append({
                        'id': market.get('id'),
                        'slug': market.get('slug'),
                        'question': market.get('question'),
                        'active': market.get('active'),
                        'closed': market.get('closed'),
                        'enableOrderBook': market.get('enableOrderBook'),
                        'clobTokenIds': market.get('clobTokenIds'),
                        'description': market.get('description', '')[:100]
                    })
                    break
    
    return matches


def main():
    print("=" * 70)
    print("🧪 测试 Solana 市场查找功能")
    print("=" * 70)
    
    gamma = GammaMarketClient()
    
    # 方法1: 通过 slug 模式查找
    print("\n方法 1: 通过 slug 模式查找")
    print("-" * 70)
    matches1 = find_solana_market_by_slug_pattern(gamma, "sol-updown-15m")
    
    if matches1:
        print(f"✅ 找到 {len(matches1)} 个匹配的市场:")
        for i, m in enumerate(matches1, 1):
            print(f"\n  市场 {i}:")
            print(f"    ID: {m['id']}")
            print(f"    Slug: {m['slug']}")
            print(f"    问题: {m['question'][:60]}...")
            print(f"    活跃: {m['active']}")
            print(f"    已关闭: {m['closed']}")
            print(f"    订单簿启用: {m['enableOrderBook']}")
            if m.get('clobTokenIds'):
                token_ids = json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'], str) else m['clobTokenIds']
                print(f"    Token IDs: {token_ids}")
    else:
        print("❌ 未找到匹配的市场")
    
    # 方法2: 通过关键词查找（现有逻辑）
    print("\n方法 2: 通过关键词查找（现有逻辑）")
    print("-" * 70)
    matches2 = find_solana_market_by_keywords(gamma)
    
    if matches2:
        print(f"✅ 找到 {len(matches2)} 个匹配的市场:")
        for i, m in enumerate(matches2, 1):
            print(f"\n  市场 {i}:")
            print(f"    ID: {m['id']}")
            print(f"    Slug: {m['slug']}")
            print(f"    问题: {m['question'][:60]}...")
            print(f"    活跃: {m['active']}")
            print(f"    已关闭: {m['closed']}")
            print(f"    订单簿启用: {m['enableOrderBook']}")
            if m.get('clobTokenIds'):
                token_ids = json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'], str) else m['clobTokenIds']
                print(f"    Token IDs: {token_ids}")
    else:
        print("❌ 未找到匹配的市场")
    
    # 合并结果，去重
    all_matches = []
    seen_ids = set()
    for m in matches1 + matches2:
        if m['id'] not in seen_ids:
            all_matches.append(m)
            seen_ids.add(m['id'])
    
    print("\n" + "=" * 70)
    print(f"📊 总结: 共找到 {len(all_matches)} 个独特的 Solana Up or Down 市场")
    print("=" * 70)
    
    if all_matches:
        print("\n所有找到的市场:")
        for i, m in enumerate(all_matches, 1):
            print(f"  {i}. {m['question'][:50]}... (Slug: {m['slug']})")
    else:
        print("\n⚠️  未找到任何 Solana Up or Down 市场")
        print("   可能的原因:")
        print("   1. 当前没有开盘的 Solana 市场")
        print("   2. 市场已关闭或归档")
        print("   3. 搜索关键词需要调整")


if __name__ == "__main__":
    main()






