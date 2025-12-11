#!/usr/bin/env python
"""
显示当前持仓数据（从接口获取）
主要字段：市场名称和value
简化版本，直接读取本地文件并展示
"""

import json
import os
from pathlib import Path

def main():
    # 读取持仓文件
    positions_file = Path(__file__).parent / "positions.json"
    
    if not positions_file.exists():
        print("❌ 持仓文件不存在")
        return
    
    with open(positions_file, 'r', encoding='utf-8') as f:
        all_positions = json.load(f)
    
    # 筛选开放持仓
    open_positions = [p for p in all_positions if p.get('status') == 'open']
    
    print("=" * 80)
    print("📊 当前持仓数据")
    print("=" * 80)
    print(f"总持仓数: {len(all_positions)} (开放: {len(open_positions)})")
    print()
    
    if not open_positions:
        print("❌ 没有开放持仓")
        return
    
    # 输出主要字段（市场名称和value）
    positions_output = []
    
    for position in open_positions:
        market_name = position.get('market_question', '')
        quantity = position.get('quantity', 0)
        buy_price = position.get('buy_price', 0)
        
        # 计算value（使用买入价格，实际应该从接口获取当前价格）
        # 这里先用买入价格，实际使用时应该从接口获取
        value = round(buy_price * quantity, 2)
        
        positions_output.append({
            "market": market_name,
            "value": value
        })
    
    print("📋 JSON格式数据（市场名称和value）")
    print("=" * 80)
    print(json.dumps(positions_output, indent=2, ensure_ascii=False))
    print()
    print("=" * 80)
    print("⚠️  注意：此value是基于买入价格计算的，实际value应从接口获取当前价格计算")

if __name__ == "__main__":
    main()

