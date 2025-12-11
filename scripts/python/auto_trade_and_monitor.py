"""
自动交易 + 止盈止损监控脚本
1. 自动选择并购买指定数量的市场
2. 添加到持仓监控
3. 启动止盈止损监控
"""

import json
import re
from datetime import datetime
from agents.polymarket.gamma import GammaMarketClient
from agents.polymarket.polymarket import Polymarket
from agents.application.executor import Executor
from langchain_core.messages import HumanMessage
from scripts.python.position_monitor import PositionManager, TAKE_PROFIT_PCT, STOP_LOSS_PCT, MONITOR_INTERVAL, AUTO_EXECUTE


# ============================================================
# 📋 交易配置 - 在这里修改
# ============================================================

NUM_TRADES = 3              # 购买市场数量
AMOUNT_PER_TRADE = 1.0      # 每个市场投资金额 (USDC)
MIN_LIQUIDITY = 5000        # 最低流动性要求
EXECUTE_TRADES = True       # 是否执行真实交易（False = 只模拟）

# ============================================================


def select_best_markets(gamma, executor, num_markets=3):
    """AI 选择最佳市场"""
    print("\n📊 获取活跃市场...")
    markets = gamma.get_all_current_markets(limit=300)
    
    # 筛选高流动性市场
    candidates = []
    for m in markets:
        liquidity = float(m.get('liquidity', 0) or 0)
        prices = m.get('outcomePrices', [])
        if isinstance(prices, str):
            prices = json.loads(prices)
        
        yes_price = float(prices[0]) if prices else 0.5
        
        # 流动性足够，价格合理
        if liquidity > MIN_LIQUIDITY and 0.15 <= yes_price <= 0.85:
            candidates.append({
                'question': m.get('question', ''),
                'liquidity': liquidity,
                'yes_price': yes_price,
                'market': m
            })
    
    # 按流动性排序
    candidates.sort(key=lambda x: x['liquidity'], reverse=True)
    candidates = candidates[:30]  # 取前 30 个
    
    print(f"   找到 {len(candidates)} 个候选市场")
    
    # AI 选择
    print("\n🤖 AI 正在选择最佳市场...")
    market_list = []
    for i, m in enumerate(candidates, 1):
        market_list.append(f"{i}. {m['question']} (Yes: {m['yes_price']:.0%}, 流动性: ${m['liquidity']/1000:.0f}k)")
    
    prompt = f'''你是专业的预测市场交易员。以下是活跃市场：

{chr(10).join(market_list)}

请选择 {num_markets} 个你最有把握预测的市场。
优先选择：政治、科技、经济类（而非纯体育博彩）
只返回市场编号，用逗号分隔。例如：1,5,12'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    selection = result.content
    print(f"   AI 选择: {selection}")
    
    # 解析选择
    indices = re.findall(r'\d+', selection)
    indices = [int(i)-1 for i in indices if int(i)-1 < len(candidates)][:num_markets]
    
    return [candidates[i] for i in indices]


def analyze_market(executor, market_info):
    """AI 分析单个市场"""
    prompt = f'''分析这个预测市场：

问题：{market_info['question']}
当前 Yes 价格：{market_info['yes_price']:.0%}

你认为 Yes 的真实概率是多少？
只返回一个 0-1 之间的数字，例如：0.65'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    
    # 解析概率
    try:
        prob = float(re.search(r'0?\.\d+', result.content).group())
    except:
        prob = 0.5
    
    # 决定买入方向
    yes_price = market_info['yes_price']
    no_price = 1 - yes_price
    
    yes_edge = prob - yes_price
    no_edge = (1 - prob) - no_price
    
    if yes_edge > no_edge:
        return {'side': 'Yes', 'ai_prob': prob, 'buy_price': yes_price, 'edge': yes_edge}
    else:
        return {'side': 'No', 'ai_prob': 1 - prob, 'buy_price': no_price, 'edge': no_edge}


def execute_trade(polymarket, market_info, decision, amount):
    """执行交易"""
    market = market_info['market']
    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        token_ids = json.loads(token_ids)
    
    # Yes = token 0, No = token 1
    token_index = 0 if decision['side'] == 'Yes' else 1
    token_id = token_ids[token_index] if token_ids else None
    
    if not token_id:
        return None, None
    
    # 计算数量（股数 = 金额 / 价格）
    quantity = amount / decision['buy_price']
    
    if not EXECUTE_TRADES:
        print(f"   📋 模拟交易: BUY {decision['side']} @ ${decision['buy_price']:.2f} x {quantity:.2f} 股")
        return token_id, quantity
    
    # 真实交易
    try:
        result = polymarket.execute_order(
            price=decision['buy_price'],
            size=quantity,
            side="BUY",
            token_id=token_id
        )
        print(f"   ✅ 交易成功: {result}")
        return token_id, quantity
    except Exception as e:
        print(f"   ❌ 交易失败: {e}")
        return None, None


def main():
    print("=" * 70)
    print("🚀 自动交易 + 止盈止损监控")
    print("=" * 70)
    
    # 显示配置
    print(f"\n📋 配置:")
    print(f"   交易数量: {NUM_TRADES} 个市场")
    print(f"   每笔金额: ${AMOUNT_PER_TRADE}")
    print(f"   总投资: ${NUM_TRADES * AMOUNT_PER_TRADE}")
    print(f"   止盈: {TAKE_PROFIT_PCT*100:.0f}%")
    print(f"   止损: {STOP_LOSS_PCT*100:.0f}%")
    print(f"   监控间隔: {MONITOR_INTERVAL} 秒")
    print(f"   执行交易: {'✅ 是' if EXECUTE_TRADES else '❌ 否（模拟）'}")
    
    # 初始化
    gamma = GammaMarketClient()
    polymarket = Polymarket()
    executor = Executor()
    pm = PositionManager()
    
    # 检查余额
    print(f"\n💳 检查余额...")
    try:
        balance = polymarket.get_usdc_balance()
        print(f"   USDC 余额: ${balance:.2f}")
        
        total_needed = NUM_TRADES * AMOUNT_PER_TRADE
        if balance < total_needed and EXECUTE_TRADES:
            print(f"   ⚠️ 余额不足！需要 ${total_needed:.2f}")
            return
    except Exception as e:
        print(f"   ⚠️ 无法获取余额: {e}")
    
    # 选择市场
    selected = select_best_markets(gamma, executor, NUM_TRADES)
    
    if len(selected) < NUM_TRADES:
        print(f"\n⚠️ 只找到 {len(selected)} 个市场")
    
    # 分析并交易
    print("\n" + "=" * 70)
    print("📈 开始交易")
    print("=" * 70)
    
    successful_trades = []
    
    for i, market_info in enumerate(selected, 1):
        print(f"\n[{i}/{len(selected)}] {market_info['question'][:50]}...")
        
        # AI 分析
        decision = analyze_market(executor, market_info)
        print(f"   AI 预测: {decision['ai_prob']:.0%} | 买入: {decision['side']} @ ${decision['buy_price']:.2f}")
        
        # 执行交易
        token_id, quantity = execute_trade(polymarket, market_info, decision, AMOUNT_PER_TRADE)
        
        if token_id:
            # 添加到持仓监控
            position, is_new = pm.add_position(
                token_id=token_id,
                market_question=market_info['question'],
                side=decision['side'],
                buy_price=decision['buy_price'],
                quantity=quantity,
                cost=AMOUNT_PER_TRADE,
            )
            successful_trades.append({
                'question': market_info['question'],
                'side': decision['side'],
                'price': decision['buy_price'],
                'quantity': quantity
            })
    
    # 显示结果
    print("\n" + "=" * 70)
    print(f"✅ 完成 {len(successful_trades)}/{len(selected)} 笔交易")
    print("=" * 70)
    
    for i, t in enumerate(successful_trades, 1):
        print(f"   {i}. {t['question'][:40]}... | {t['side']} @ ${t['price']:.2f}")
    
    # 显示持仓
    pm.display_positions()
    
    # 启动监控
    if successful_trades:
        print("\n" + "=" * 70)
        print("🔄 启动止盈止损监控")
        print("=" * 70)
        pm.monitor_loop()


if __name__ == "__main__":
    main()




