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
    order_id: str = ""      # 订单 ID
    
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
        order_id: str = "",             # 订单 ID
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
            status="open",
            order_id=order_id
        )
        
        self.positions.append(position)
        self.save_positions()
        return position
    
    def get_current_price(self, token_id: str) -> Optional[float]:
        """获取当前卖出价格（Bid 价格 - 订单簿最高买单）"""
        
        # 方法 1: 通过订单簿获取 Bid 价格（最准确的卖出价）
        try:
            orderbook = self.polymarket.client.get_order_book(token_id)
            if orderbook and orderbook.bids:
                # bids 可能没有排序，需要找最高价
                best_bid = max(orderbook.bids, key=lambda x: float(x.price))
                return float(best_bid.price)
        except Exception as e:
            print(f"⚠️ 订单簿获取失败: {e}")
        
        # 方法 2: 备用 - 通过 Gamma API 获取中间价
        import httpx
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
            "reason": None,
            "order_id": getattr(position, 'order_id', '')  # 订单 ID
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
    
    def sync_stop_loss_take_profit(self):
        """同步所有持仓的止盈止损价格（根据当前配置）"""
        updated_count = 0
        for p in self.positions:
            if p.status == "open":
                old_tp = p.take_profit
                old_sl = p.stop_loss
                
                # 重新计算
                new_tp = min(p.buy_price * (1 + TAKE_PROFIT_PCT), 0.99) if TAKE_PROFIT_PCT > 0 else 0
                new_sl = max(p.buy_price * (1 - STOP_LOSS_PCT), 0.01) if STOP_LOSS_PCT > 0 else 0
                
                # 更新
                if abs(new_tp - old_tp) > 0.001 or abs(new_sl - old_sl) > 0.001:
                    p.take_profit = round(new_tp, 4)
                    p.stop_loss = round(new_sl, 4)
                    updated_count += 1
        
        if updated_count > 0:
            self.save_positions()
            print(f"🔄 已同步 {updated_count} 个持仓的止盈止损价格")
            print(f"   止盈: +{TAKE_PROFIT_PCT*100:.0f}% | 止损: -{STOP_LOSS_PCT*100:.0f}%")
            print()
        
        return updated_count
    
    def get_token_balance(self, token_id: str, wallet: str = "api") -> float:
        """
        获取 outcome token 余额
        
        Args:
            token_id: Token ID
            wallet: "api" = API私钥钱包, "proxy" = 网页代理钱包, "both" = 两者之和
        """
        try:
            balance_abi = '[{"inputs": [{"name": "account", "type": "address"}, {"name": "id", "type": "uint256"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]'
            ctf = self.polymarket.web3.eth.contract(address=self.polymarket.ctf_address, abi=balance_abi)
            
            api_balance = 0.0
            proxy_balance = 0.0
            
            # API 钱包余额
            if wallet in ("api", "both"):
                api_addr = self.polymarket.client.get_address()
                api_balance = ctf.functions.balanceOf(api_addr, int(token_id)).call() / 1e6
            
            # 代理钱包余额
            if wallet in ("proxy", "both"):
                proxy_addr = os.getenv("POLYMARKET_PROXY_WALLET")
                if proxy_addr:
                    proxy_balance = ctf.functions.balanceOf(proxy_addr, int(token_id)).call() / 1e6
            
            if wallet == "api":
                return api_balance
            elif wallet == "proxy":
                return proxy_balance
            else:
                return api_balance + proxy_balance
                
        except Exception as e:
            print(f"⚠️ 无法获取 token 余额: {e}")
            return 0.0
    
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
        
        # 检查 token 余额
        api_balance = self.get_token_balance(position.token_id, wallet="api")
        proxy_balance = self.get_token_balance(position.token_id, wallet="proxy")
        
        # 使用实际余额（容忍小的精度差异）
        sell_quantity = api_balance if api_balance > 0 else position.quantity
        
        print(f"⚠️ 准备卖出: {position.market_question[:40]}...")
        print(f"   原因: {reason}")
        print(f"   记录数量: {position.quantity}")
        print(f"   实际数量: {sell_quantity:.4f}")
        print(f"   买入价: ${position.buy_price:.2f}")
        print(f"   当前价: ${current_price:.2f}")
        
        pnl = (current_price - position.buy_price) * sell_quantity
        print(f"   预计盈亏: ${pnl:+.2f}")
        
        if not execute:
            print("   📋 模拟模式 - 未执行实际交易")
            return {"status": "simulated", "reason": reason, "pnl": pnl}
        
        # 检查余额是否足够
        if api_balance < 0.01:  # 余额太少
            print(f"   ❌ API 钱包 token 余额不足!")
            print(f"      记录数量: {position.quantity}")
            print(f"      API钱包余额: {api_balance}")
            print(f"      代理钱包余额: {proxy_balance}")
            
            if proxy_balance >= position.quantity * 0.99:  # 允许1%误差
                print(f"   💡 Token 在代理钱包中，请在 Polymarket 网页上卖出")
                return {"status": "error", "reason": f"Token在代理钱包中，请在网页卖出"}
            else:
                print(f"   💡 请在 Polymarket 网页上手动卖出，或通过 API 购买新订单")
                return {"status": "error", "reason": f"API钱包余额不足"}
        
        # 真实卖出（使用实际余额）
        try:
            result = self.polymarket.execute_order(
                price=current_price,
                size=sell_quantity,
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
        print()
        
        # 同步所有持仓的止盈止损价格
        self.sync_stop_loss_take_profit()
        
        try:
            check_count = 0
            while True:
                check_count += 1
                results = self.check_all_positions()
                
                print()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check #{check_count}")
                
                # 表格分隔线
                sep = "+----------+------------------------------+------+--------+--------+--------+--------+---------+"
                print(sep)
                print(f"| {'OrderID':<8} | {'Market':<28} | {'Side':<4} | {'Buy':>6} | {'Now':>6} | {'Cost':>6} | {'Value':>6} | {'P&L':>7} |")
                print(sep)
                
                total_cost = 0
                total_value = 0
                
                for r in results:
                    question = r['question'][:25] + "..." if len(r['question']) > 28 else r['question']
                    pnl_pct = r['pnl_pct'] * 100
                    current_value = r['current_price'] * r['quantity']
                    cost = r['cost']
                    order_id = r.get('order_id', '')[:8] if r.get('order_id') else '-'
                    
                    total_cost += cost
                    total_value += current_value
                    
                    buy_str = f"${r['buy_price']:.2f}"
                    cur_str = f"${r['current_price']:.2f}"
                    cost_str = f"${cost:.2f}"
                    value_str = f"${current_value:.2f}"
                    pnl_str = f"{pnl_pct:+.1f}%"
                    
                    print(f"| {order_id:<8} | {question:<28} | {r['side']:<4} | {buy_str:>6} | {cur_str:>6} | {cost_str:>6} | {value_str:>6} | {pnl_str:>7} |")
                    
                    # 触发止盈止损
                    if r.get("action") == "SELL":
                        print(f"|          >>> 触发: {r['reason']:<67} |")
                        
                        # 找到对应持仓并执行
                        for p in self.positions:
                            if p.token_id == r['token_id'] and p.status == "open":
                                self.execute_sell(p, r['reason'], execute=auto_execute)
                                break
                
                print(sep)
                total_pnl = total_value - total_cost
                total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
                print(f"| {'TOTAL':<8} | {'':<28} | {'':<4} | {'':<6} | {'':<6} | {'$'+f'{total_cost:.2f}':>6} | {'$'+f'{total_value:.2f}':>6} | {f'{total_pnl_pct:+.1f}%':>7} |")
                print(sep)
                print(f"  Next check in {interval_seconds}s")
                
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
