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
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

def main():
    print("=" * 80)
    print("📊 当前持仓数据（从接口获取）")
    print("=" * 80)
    print()
    
    try:
        from scripts.python.position_monitor import PositionManager
        
        pm = PositionManager()
        pm.load_positions()
        
        open_positions = [p for p in pm.positions if p.status == "open"]
        
        if not open_positions:
            print("❌ 没有开放持仓")
            return
        
        print(f"总持仓数: {len(open_positions)}")
        print()
        
        positions_data = []
        total_value = 0
        
        for i, position in enumerate(open_positions, 1):
            print(f"[{i}/{len(open_positions)}] 正在获取 {position.market_question[:50]}... 的数据")
            
            # 从接口获取当前价格（订单簿API）
            current_price = pm.get_current_price(position.token_id)
            if current_price is None:
                current_price = position.buy_price
                price_source = "本地（接口获取失败）"
            else:
                price_source = "接口（订单簿）"
            
            # 从区块链接口获取实际数量
            try:
                actual_quantity = pm.get_token_balance(position.token_id, wallet="both")
                if actual_quantity > 0.0001:
                    quantity = round(actual_quantity, 6)
                    quantity_source = "接口（区块链）"
                else:
                    quantity = position.quantity
                    quantity_source = "本地"
            except Exception as e:
                quantity = position.quantity
                quantity_source = "本地（错误）"
            
            # 计算value：接口价格 × 接口数量
            value = round(current_price * quantity, 6)
            total_value += value
            
            position_info = {
                "market": position.market_question,
                "shares": round(quantity, 6),  # 持仓数量
                "value": round(value, 2)  # 当前价值（保留2位小数，与官方显示一致）
            }
            
            positions_data.append(position_info)
            
            print(f"   ✅ {position.market_question[:60]}")
            print(f"      Shares: {quantity:.6f} | Value: ${value:.2f} | 价格: ${current_price:.4f} ({price_source})")
            print()
        
        print("=" * 80)
        print(f"📊 汇总: 总Value = ${total_value:.2f}")
        print("=" * 80)
        print()
        
        # 输出JSON格式数据（市场名称、持仓和value）
        print("=" * 80)
        print("📋 JSON格式数据（市场名称、持仓和当前价值）")
        print("=" * 80)
        print(json.dumps(positions_data, indent=2, ensure_ascii=False))
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装所有依赖并激活虚拟环境")
        print("运行: source .venv/bin/activate")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

