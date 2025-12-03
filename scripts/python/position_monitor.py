"""
持仓监控与止盈止损模块
- 记录买入持仓
- 定期监控价格变化
- 自动止盈止损卖出
"""

import json
import time
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
from agents.polymarket.polymarket import Polymarket
from agents.polymarket.gamma import GammaMarketClient

# 加载 .env 配置（override=True 确保覆盖已有环境变量）
load_dotenv(override=True)

# ============================================================
# 📋 配置参数 - 从 .env 文件读取
# ============================================================

# 止盈止损设置
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.20"))    # 止盈百分比
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.10"))        # 止损百分比

# 监控设置
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "30"))      # 检查间隔（秒）
AUTO_EXECUTE = os.getenv("AUTO_EXECUTE", "false").lower() == "true"  # 是否自动执行

# 文件路径
POSITIONS_FILE = os.path.join(os.path.dirname(__file__), "positions.json")

# ============================================================


@dataclass
class Position:
    """单个持仓"""
    token_id: str           # 代币 ID
    market_question: str    # 市场问题
    side: str               # Yes 或 No
    buy_price: float        # 买入价格
    quantity: float         # 持有数量（股）
    cost: float             # 成本（USDC）
    buy_time: str           # 买入时间
    take_profit: float      # 止盈价格 (0 = 不设)
    stop_loss: float        # 止损价格 (0 = 不设)
    status: str = "open"    # open, closed, expired
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class PositionManager:
    """持仓管理器"""
    
    def __init__(self):
        self.polymarket = Polymarket()
        self.gamma = GammaMarketClient()
        self.positions: list[Position] = []
        self.load_positions()
    
    def load_positions(self):
        """从文件加载持仓"""
        if os.path.exists(POSITIONS_FILE):
            try:
                with open(POSITIONS_FILE, 'r') as f:
                    data = json.load(f)
                    self.positions = [Position.from_dict(p) for p in data]
            except:
                self.positions = []
        else:
            self.positions = []
    
    def save_positions(self):
        """保存持仓到文件"""
        with open(POSITIONS_FILE, 'w') as f:
            json.dump([p.to_dict() for p in self.positions], f, indent=2)
    
    def add_position(
        self,
        token_id: str,
        market_question: str,
        side: str,
        buy_price: float,
        quantity: float,
        cost: float,
        take_profit_pct: float = None,  # 止盈百分比，None 使用默认值
        stop_loss_pct: float = None,    # 止损百分比，None 使用默认值
    ):
        """添加持仓"""
        # 使用默认配置
        if take_profit_pct is None:
            take_profit_pct = TAKE_PROFIT_PCT
        if stop_loss_pct is None:
            stop_loss_pct = STOP_LOSS_PCT
        # 计算止盈止损价格
        take_profit = 0
        stop_loss = 0
        
        if take_profit_pct > 0:
            take_profit = min(buy_price * (1 + take_profit_pct), 0.99)
        
        if stop_loss_pct > 0:
            stop_loss = max(buy_price * (1 - stop_loss_pct), 0.01)
        
        position = Position(
            token_id=token_id,
            market_question=market_question,
            side=side,
            buy_price=buy_price,
            quantity=quantity,
            cost=cost,
            buy_time=datetime.utcnow().isoformat(),
            take_profit=take_profit,
            stop_loss=stop_loss,
            status="open"
        )
        
        self.positions.append(position)
        self.save_positions()
        return position
    
    def get_current_price(self, token_id: str) -> Optional[float]:
        """获取当前市场价格"""
        import httpx
        
        # 方法 1: 通过 Gamma API 获取（最准确）
        try:
            url = f'https://gamma-api.polymarket.com/markets?clob_token_ids={token_id}'
            resp = httpx.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    prices = data[0].get('outcomePrices', [])
                    if isinstance(prices, str):
                        prices = json.loads(prices)
                    if prices:
                        return float(prices[0])  # Yes 价格
        except:
            pass
        
        # 方法 2: 通过市场数据获取
        try:
            market = self.polymarket.get_market(token_id)
            if market:
                prices = market.get('outcome_prices', market.get('outcomePrices', []))
                if isinstance(prices, str):
                    prices = json.loads(prices)
                if prices:
                    return float(prices[0])
        except:
            pass
        
        return None
    
    def check_position(self, position: Position) -> dict:
        """检查单个持仓状态"""
        result = {
            "token_id": position.token_id,
            "question": position.market_question,
            "side": position.side,
            "buy_price": position.buy_price,
            "quantity": position.quantity,
            "cost": position.cost,
            "take_profit": position.take_profit,
            "stop_loss": position.stop_loss,
            "current_price": position.buy_price,  # 默认为买入价
            "pnl_pct": 0,
            "pnl_value": 0,
            "action": None,
            "reason": None
        }
        
        if position.status != "open":
            result["reason"] = "已关闭"
            return result
        
        current_price = self.get_current_price(position.token_id)
        if current_price is None:
            result["reason"] = "无法获取价格"
            current_price = position.buy_price  # 使用买入价
        
        result["current_price"] = current_price
        
        # 计算盈亏
        pnl_pct = (current_price - position.buy_price) / position.buy_price
        pnl_value = (current_price - position.buy_price) * position.quantity
        
        result["pnl_pct"] = pnl_pct
        result["pnl_value"] = pnl_value
        
        # 检查止盈
        if position.take_profit > 0 and current_price >= position.take_profit:
            result["action"] = "SELL"
            result["reason"] = f"🟢 止盈触发！目标价 ${position.take_profit:.2f}"
        
        # 检查止损
        elif position.stop_loss > 0 and current_price <= position.stop_loss:
            result["action"] = "SELL"
            result["reason"] = f"🔴 止损触发！目标价 ${position.stop_loss:.2f}"
        
        return result
    
    def check_all_positions(self) -> list[dict]:
        """检查所有持仓"""
        results = []
        for p in self.positions:
            if p.status == "open":
                results.append(self.check_position(p))
        return results
    
    def close_position(self, token_id: str, reason: str = "手动关闭"):
        """关闭持仓（标记为已关闭）"""
        for p in self.positions:
            if p.token_id == token_id and p.status == "open":
                p.status = "closed"
                self.save_positions()
                return True
        return False
    
    def execute_sell(self, position: Position, reason: str, execute: bool = False) -> dict:
        """
        执行卖出
        
        Args:
            position: 持仓对象
            reason: 卖出原因
            execute: 是否真正执行（False = 模拟）
        """
        current_price = self.get_current_price(position.token_id)
        if current_price is None:
            return {"status": "error", "reason": "无法获取当前价格"}
        
        print(f"⚠️ 准备卖出: {position.market_question[:40]}...")
        print(f"   原因: {reason}")
        print(f"   数量: {position.quantity}")
        print(f"   买入价: ${position.buy_price:.2f}")
        print(f"   当前价: ${current_price:.2f}")
        
        pnl = (current_price - position.buy_price) * position.quantity
        print(f"   预计盈亏: ${pnl:+.2f}")
        
        if not execute:
            print("   📋 模拟模式 - 未执行实际交易")
            return {"status": "simulated", "reason": reason, "pnl": pnl}
        
        # 真实卖出
        try:
            result = self.polymarket.execute_order(
                price=current_price,
                size=position.quantity,
                side="SELL",
                token_id=position.token_id
            )
            
            # 标记持仓已关闭
            position.status = "closed"
            self.save_positions()
            
            print(f"   ✅ 卖出成功!")
            return {"status": "success", "reason": reason, "pnl": pnl, "result": result}
            
        except Exception as e:
            print(f"   ❌ 卖出失败: {e}")
            return {"status": "error", "reason": str(e)}
    
    def display_positions(self):
        """显示所有持仓"""
        print()
        print("=" * 80)
        print("📊 当前持仓")
        print("=" * 80)
        
        open_positions = [p for p in self.positions if p.status == "open"]
        
        if not open_positions:
            print("没有持仓")
            return
        
        print()
        print(f"{'#':<3} {'市场':<35} {'方向':<5} {'买价':<7} {'现价':<7} {'盈亏':<8} {'止盈':<7} {'止损':<7}")
        print("-" * 90)
        
        total_cost = 0
        total_value = 0
        
        for i, p in enumerate(open_positions, 1):
            current_price = self.get_current_price(p.token_id)
            if current_price is None:
                current_price = p.buy_price
            
            pnl_pct = (current_price - p.buy_price) / p.buy_price * 100
            current_value = current_price * p.quantity
            
            total_cost += p.cost
            total_value += current_value
            
            q = p.market_question[:32] + "..." if len(p.market_question) > 35 else p.market_question
            tp = f"${p.take_profit:.2f}" if p.take_profit > 0 else "-"
            sl = f"${p.stop_loss:.2f}" if p.stop_loss > 0 else "-"
            pnl_str = f"{pnl_pct:+.1f}%"
            
            print(f"{i:<3} {q:<35} {p.side:<5} ${p.buy_price:.2f}  ${current_price:.2f}  {pnl_str:<8} {tp:<7} {sl:<7}")
        
        print("-" * 90)
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        print(f"总成本: ${total_cost:.2f} | 当前价值: ${total_value:.2f} | 盈亏: ${total_pnl:+.2f} ({total_pnl_pct:+.1f}%)")
        print()
    
    def monitor_loop(self, interval_seconds: int = None, auto_execute: bool = None):
        """
        持续监控循环
        
        Args:
            interval_seconds: 检查间隔（秒），None 使用默认值
            auto_execute: 是否自动执行止盈止损，None 使用默认值
        """
        # 使用默认配置
        if interval_seconds is None:
            interval_seconds = MONITOR_INTERVAL
        if auto_execute is None:
            auto_execute = AUTO_EXECUTE
        
        print()
        print("=" * 70)
        print("🔄 启动持仓监控")
        print("=" * 70)
        print(f"   检查间隔: {interval_seconds} 秒")
        print(f"   自动交易: {'✅ 开启（真实交易！）' if auto_execute else '❌ 关闭（仅提醒）'}")
        print(f"   止盈阈值: +{TAKE_PROFIT_PCT*100:.0f}%")
        print(f"   止损阈值: -{STOP_LOSS_PCT*100:.0f}%")
        print("   按 Ctrl+C 停止")
        print("=" * 70)
        
        try:
            check_count = 0
            while True:
                check_count += 1
                results = self.check_all_positions()
                
                print()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 第 {check_count} 次检查")
                print("-" * 70)
                print(f"{'市场':<40} {'方向':<5} {'买入':<7} {'现价':<7} {'盈亏':<10} {'状态'}")
                print("-" * 70)
                
                total_cost = 0
                total_value = 0
                
                for r in results:
                    question = r['question'][:37] + "..." if len(r['question']) > 40 else r['question']
                    pnl_pct = r['pnl_pct'] * 100
                    current_value = r['current_price'] * r['quantity']
                    
                    total_cost += r['cost']
                    total_value += current_value
                    
                    # 状态显示
                    if r.get("action") == "SELL":
                        status = f"🚨 {r['reason']}"
                    elif pnl_pct > 0:
                        status = "📈 盈利"
                    elif pnl_pct < 0:
                        status = "📉 亏损"
                    else:
                        status = "➖ 持平"
                    
                    print(f"{question:<40} {r['side']:<5} ${r['buy_price']:.2f}  ${r['current_price']:.2f}  {pnl_pct:+.1f}%      {status}")
                    
                    # 触发止盈止损
                    if r.get("action") == "SELL":
                        print(f"   >>> 触发条件: {r['reason']}")
                        
                        # 找到对应持仓并执行
                        for p in self.positions:
                            if p.token_id == r['token_id'] and p.status == "open":
                                self.execute_sell(p, r['reason'], execute=auto_execute)
                                break
                
                print("-" * 70)
                total_pnl = total_value - total_cost
                total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
                print(f"总计: 成本 ${total_cost:.2f} | 现值 ${total_value:.2f} | 盈亏 ${total_pnl:+.2f} ({total_pnl_pct:+.1f}%)")
                print(f"下次检查: {interval_seconds} 秒后")
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print()
            print("=" * 70)
            print("⏹ 监控已停止")
            print("=" * 70)
    
    def set_stop_loss_take_profit(self, token_id: str, take_profit_pct: float = 0, stop_loss_pct: float = 0):
        """
        为现有持仓设置止盈止损
        
        Args:
            token_id: 代币 ID
            take_profit_pct: 止盈百分比（如 0.2 = 涨 20%）
            stop_loss_pct: 止损百分比（如 0.1 = 跌 10%）
        """
        for p in self.positions:
            if p.token_id == token_id and p.status == "open":
                if take_profit_pct > 0:
                    p.take_profit = min(p.buy_price * (1 + take_profit_pct), 0.99)
                if stop_loss_pct > 0:
                    p.stop_loss = max(p.buy_price * (1 - stop_loss_pct), 0.01)
                self.save_positions()
                print(f"✅ 已设置: 止盈=${p.take_profit:.2f}, 止损=${p.stop_loss:.2f}")
                return True
        print("❌ 未找到持仓")
        return False


def show_config():
    """显示当前配置"""
    print()
    print("=" * 60)
    print("📋 当前配置")
    print("=" * 60)
    print(f"  止盈百分比: {TAKE_PROFIT_PCT * 100:.0f}%")
    print(f"  止损百分比: {STOP_LOSS_PCT * 100:.0f}%")
    print(f"  监控间隔: {MONITOR_INTERVAL} 秒")
    print(f"  自动执行: {'✅ 开启' if AUTO_EXECUTE else '❌ 关闭'}")
    print(f"  持仓文件: {POSITIONS_FILE}")
    print("=" * 60)


def start_monitor():
    """启动监控"""
    show_config()
    
    pm = PositionManager()
    pm.display_positions()
    
    if pm.positions:
        pm.monitor_loop()
    else:
        print("⚠️ 没有持仓，无需监控")


if __name__ == "__main__":
    show_config()
    
    pm = PositionManager()
    pm.display_positions()
    
    print()
    print("💡 使用方法:")
    print("   1. 修改文件顶部的配置参数")
    print("   2. 买入后调用 pm.add_position() 添加持仓")
    print("   3. 调用 pm.monitor_loop() 启动监控")
    print()
