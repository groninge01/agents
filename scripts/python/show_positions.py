#!/usr/bin/env python
"""
显示当前持仓数据（从接口获取）
主要字段：市场名称和value
"""

import sys
import os
import json

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 尝试导入，如果失败则给出提示
try:
    from scripts.python.position_monitor import PositionManager
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保已安装所有依赖并激活虚拟环境")
    sys.exit(1)

def main():
    print("=" * 80)
    print("📊 当前持仓数据（从接口获取）")
    print("=" * 80)
    print()
    
    try:
        pm = PositionManager()
        pm.load_positions()
        
        open_positions = [p for p in pm.positions if p.status == "open"]
        
        if not open_positions:
            print("❌ 没有开放持仓")
            return
        
        print(f"总持仓数: {len(open_positions)}")
        print()
        print(f"{'市场名称':<60} {'Value (USDC)':>15} {'数量':>12} {'当前价格':>12}")
        print("-" * 100)
        
        positions_data = []
        total_value = 0
        
        for position in open_positions:
            # 从接口获取当前价格
            current_price = pm.get_current_price(position.token_id)
            if current_price is None:
                current_price = position.buy_price
                price_source = "本地（接口获取失败）"
            else:
                price_source = "接口"
            
            # 从区块链接口获取实际数量
            actual_quantity = pm.get_token_balance(position.token_id, wallet="both")
            if actual_quantity > 0.0001:
                quantity = round(actual_quantity, 6)
                quantity_source = "接口"
            else:
                quantity = position.quantity
                quantity_source = "本地"
            
            # 计算value：接口价格 × 接口数量
            value = round(current_price * quantity, 6)
            total_value += value
            
            market_name = position.market_question
            if len(market_name) > 58:
                market_name = market_name[:55] + "..."
            
            position_info = {
                "market_question": position.market_question,
                "value": value,
                "quantity": quantity,
                "current_price": current_price,
                "quantity_source": quantity_source,
                "price_source": price_source,
                "token_id": position.token_id[:20] + "..."
            }
            
            positions_data.append(position_info)
            
            print(f"{market_name:<60} ${value:>14.4f} {quantity:>12.6f} ${current_price:>11.4f} ({price_source})")
        
        print("-" * 100)
        print(f"{'总计':<60} ${total_value:>14.4f}")
        print()
        
        # 输出JSON格式数据
        print("=" * 80)
        print("📋 JSON格式数据（仅市场名称和value）")
        print("=" * 80)
        
        # 只输出主要字段
        simplified_data = [
            {
                "market": pos["market_question"],
                "value": pos["value"]
            }
            for pos in positions_data
        ]
        
        print(json.dumps(simplified_data, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

