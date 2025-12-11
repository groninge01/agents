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

# 止盈止损设置（从 .env 文件读取）
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.30"))    # 止盈百分比：默认 30%
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.15"))        # 止损百分比：默认 15%

# 监控设置（从 .env 文件读取）
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "1"))       # 检查间隔（秒）：默认 1 秒
AUTO_EXECUTE = os.getenv("AUTO_EXECUTE", "true").lower() == "true"  # 是否自动执行：默认 true

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
        """从文件加载持仓（强制从磁盘读取最新数据）"""
        if os.path.exists(POSITIONS_FILE):
            try:
                # 使用文件锁确保读取到最新数据
                import time
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        with open(POSITIONS_FILE, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.positions = [Position.from_dict(p) for p in data]
                        break  # 成功读取
                    except (json.JSONDecodeError, IOError) as e:
                        if attempt < max_retries - 1:
                            time.sleep(0.1)  # 等待文件写入完成
                            continue
                        else:
                            raise
            except Exception as e:
                print(f"⚠️ 加载持仓文件失败: {e}")
                self.positions = []
        else:
            self.positions = []
    
    def save_positions(self):
        """保存持仓到文件（使用原子写入，确保数据完整性）"""
        import time
        # 使用原子写入，避免并发问题
        temp_file = POSITIONS_FILE + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump([p.to_dict() for p in self.positions], f, indent=2, ensure_ascii=False)
                f.flush()  # 强制刷新缓冲区
                os.fsync(f.fileno())  # 强制同步到磁盘
            
            # 原子性重命名
            os.replace(temp_file, POSITIONS_FILE)
            # 确保文件系统同步
            try:
                os.sync()  # Linux系统调用，强制同步文件系统
            except:
                pass
        except Exception as e:
            # 如果失败，尝试直接写入
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            try:
                with open(POSITIONS_FILE, 'w', encoding='utf-8') as f:
                    json.dump([p.to_dict() for p in self.positions], f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as e2:
                print(f"⚠️ 保存持仓文件失败: {e2}")
    
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
        """添加持仓（自动去重）
        
        Returns:
            tuple: (position, is_new) - 持仓对象和是否为新添加
        """
        # 重新加载数据，确保使用最新的持仓列表
        self.load_positions()
        
        # 检查是否已存在相同的持仓（通过order_id或token_id+status）
        if order_id:
            # 优先通过order_id检查
            existing = next((p for p in self.positions if p.order_id == order_id and p.order_id), None)
            if existing:
                print(f"⚠️  订单 {order_id[:20]}... 已存在，跳过添加")
                return existing, False
        
        # 检查是否已存在相同的token_id且状态为open的持仓
        existing_open = next((p for p in self.positions if p.token_id == token_id and p.status == "open"), None)
        if existing_open:
            # 合并持仓：累加shares数量和cost，使用加权平均价格
            print(f"📝 发现已有持仓，合并数量: {existing_open.market_question[:40]}...")
            print(f"   原持仓: {existing_open.quantity:.6f} 股 @ ${existing_open.buy_price:.4f}, 成本 ${existing_open.cost:.4f}")
            print(f"   新交易: {quantity:.6f} 股 @ ${buy_price:.4f}, 成本 ${cost:.4f}")
            
            # 合并shares数量（累加）
            total_quantity = round(existing_open.quantity + quantity, 6)  # 保留6位小数精度
            
            # 累加cost（每次交易的固定成本都要累加）
            total_cost = round(existing_open.cost + cost, 6)  # 保留6位小数精度，累加所有交易成本
            
            # 计算加权平均买入价格（官方算法）：(原数量 * 原价格 + 新数量 * 新价格) / 总数量
            if total_quantity > 0:
                weighted_price = (
                    existing_open.quantity * existing_open.buy_price + 
                    quantity * buy_price
                ) / total_quantity
                new_avg_buy_price = round(weighted_price, 6)  # 保留6位小数，注意精度
            else:
                new_avg_buy_price = buy_price
            
            # 更新持仓：累加shares和cost，更新加权平均价格
            existing_open.quantity = total_quantity
            existing_open.buy_price = new_avg_buy_price
            existing_open.cost = total_cost  # 累加所有交易的cost
            existing_open.buy_time = datetime.utcnow().isoformat()  # 更新时间为最新交易时间
            
            # 重新计算止盈止损价格（基于新的加权平均买入价）
            if take_profit_pct is None:
                take_profit_pct = TAKE_PROFIT_PCT
            if stop_loss_pct is None:
                stop_loss_pct = STOP_LOSS_PCT
            
            if take_profit_pct > 0:
                existing_open.take_profit = round(min(new_avg_buy_price * (1 + take_profit_pct), 0.99), 6)
            if stop_loss_pct > 0:
                existing_open.stop_loss = round(max(new_avg_buy_price * (1 - stop_loss_pct), 0.01), 6)
            
            print(f"   ✅ 合并后: {total_quantity:.6f} 股 @ ${new_avg_buy_price:.4f} (加权平均), 累计成本 ${total_cost:.4f}")
            
            # 保存更新后的持仓
            self.save_positions()
            return existing_open, False  # 返回 False 表示不是新添加的，但已更新
        
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
        return position, True
    
    def get_current_price(self, token_id: str) -> Optional[float]:
        """从接口获取当前卖出价格（Bid 价格 - 订单簿最高买单）"""
        
        # 方法 1: 通过订单簿API获取 Bid 价格（最准确的卖出价，与官方一致）
        try:
            orderbook = self.polymarket.get_orderbook(token_id)  # 使用包装的方法，会自动记录日志
            if orderbook and orderbook.bids:
                # bids 可能没有排序，需要找最高价（best bid）
                best_bid = max(orderbook.bids, key=lambda x: float(x.price))
                return float(best_bid.price)
        except Exception as e:
            pass  # 静默失败，继续尝试其他方法
        
        # 方法 2: 通过 Gamma API 获取市场价格
        # ⚠️ 重要：需要根据 token_id 找到对应的 outcome 索引，而不是总是用 prices[0]
        import httpx
        import time
        from agents.utils.api_logger import log_http_request, log_http_response
        
        try:
            url = f'https://gamma-api.polymarket.com/markets?clob_token_ids={token_id}'
            log_http_request("GET", url)
            start_time = time.time()
            
            resp = httpx.get(url, timeout=10)
            elapsed_time = time.time() - start_time
            
            if resp.status_code == 200:
                data = resp.json()
                log_http_response(resp.status_code, f"Token ID: {token_id}", elapsed_time)
                
                if data and len(data) > 0:
                    market = data[0]
                    
                    # 获取 token IDs 列表
                    token_ids_list = market.get('clobTokenIds', [])
                    if isinstance(token_ids_list, str):
                        token_ids_list = json.loads(token_ids_list)
                    
                    # 获取价格列表
                    prices = market.get('outcomePrices', [])
                    if isinstance(prices, str):
                        prices = json.loads(prices)
                    
                    # 找到 token_id 在列表中的索引
                    if token_ids_list and prices and len(token_ids_list) == len(prices):
                        try:
                            # 尝试找到匹配的索引
                            token_idx = token_ids_list.index(token_id)
                            if token_idx < len(prices):
                                return float(prices[token_idx])
                        except (ValueError, IndexError):
                            # 如果找不到，使用第一个价格作为备用（但应该警告）
                            if len(prices) > 0:
                                print(f"⚠️ 警告: 无法找到 token_id {token_id[:20]}... 在 outcomes 中的索引，使用 prices[0]")
                                return float(prices[0])
                    elif prices and len(prices) > 0:
                        # 如果没有 token_ids 列表，使用第一个价格（旧逻辑，但可能不准确）
                        print(f"⚠️ 警告: 无法获取 token_ids 列表，使用 prices[0]（可能不准确）")
                        return float(prices[0])
        except Exception as e:
            pass
        
        return None
    
    def get_position_value_from_api(self, token_id: str, quantity: float) -> Optional[float]:
        """
        从接口获取持仓的当前价值
        
        Args:
            token_id: Token ID
            quantity: 持仓数量
            
        Returns:
            当前价值（USDC），如果无法获取则返回None
        """
        # 从接口获取当前价格
        current_price = self.get_current_price(token_id)
        
        if current_price is None:
            return None
        
        # 使用接口价格计算价值（与官方算法一致）
        return round(current_price * quantity, 6)
    
    def check_position(self, position: Position) -> dict:
        """检查单个持仓状态（使用接口数据）"""
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
        
        # 从接口获取当前价格（订单簿API）
        current_price = self.get_current_price(position.token_id)
        if current_price is None:
            result["reason"] = "无法获取价格"
            current_price = position.buy_price  # 使用买入价
        
        result["current_price"] = current_price
        
        # 从区块链接口获取实际持仓数量（实时数据）
        actual_quantity = self.get_token_balance(position.token_id, wallet="both")
        if actual_quantity > 0:
            # 使用接口返回的实际数量
            result["quantity"] = round(actual_quantity, 6)
        else:
            # 如果没有余额，使用本地记录的数量
            result["quantity"] = position.quantity
        
        # 使用接口数据计算盈亏（接口价格 × 接口数量）
        pnl_pct = (current_price - position.buy_price) / position.buy_price
        pnl_value = (current_price - position.buy_price) * result["quantity"]
        
        result["pnl_pct"] = pnl_pct
        result["pnl_value"] = pnl_value
        
        # 检查止盈：使用配置的止盈百分比
        if TAKE_PROFIT_PCT > 0 and pnl_pct >= TAKE_PROFIT_PCT:
            result["action"] = "SELL"
            result["reason"] = f"🟢 止盈触发！涨幅 {pnl_pct*100:.1f}% >= {TAKE_PROFIT_PCT*100:.0f}%"
        
        # 检查止损：使用配置的止损百分比
        elif STOP_LOSS_PCT > 0 and pnl_pct <= -STOP_LOSS_PCT:
            result["action"] = "SELL"
            result["reason"] = f"🔴 止损触发！跌幅 {abs(pnl_pct)*100:.1f}% >= {STOP_LOSS_PCT*100:.0f}%"
        
        # 兼容旧的止盈止损价格检查（如果设置了）
        elif position.take_profit > 0 and current_price >= position.take_profit:
            result["action"] = "SELL"
            result["reason"] = f"🟢 止盈触发！目标价 ${position.take_profit:.2f}"
        
        elif position.stop_loss > 0 and current_price <= position.stop_loss:
            result["action"] = "SELL"
            result["reason"] = f"🔴 止损触发！目标价 ${position.stop_loss:.2f}"
        
        return result
    
    def sync_positions_from_blockchain(self):
        """
        从区块链同步实际持仓数据
        对比本地记录和实际余额，更新差异
        """
        print("🔄 从区块链同步持仓数据...")
        self.load_positions()
        
        # 获取所有钱包地址
        api_addr = self.polymarket.client.get_address()
        proxy_addr = os.getenv("POLYMARKET_PROXY_WALLET")
        
        # 获取所有开放持仓的token_id
        open_positions = [p for p in self.positions if p.status == "open"]
        token_ids = list(set([p.token_id for p in open_positions]))
        
        updated_count = 0
        new_positions = []
        
        # 检查每个token的实际余额
        for token_id in token_ids:
            try:
                # 获取实际余额（API钱包 + 代理钱包）
                api_balance = self.get_token_balance(token_id, wallet="api")
                proxy_balance = self.get_token_balance(token_id, wallet="proxy") if proxy_addr else 0.0
                actual_balance = api_balance + proxy_balance
                
                # 找到本地记录的所有该token的持仓
                local_positions = [p for p in open_positions if p.token_id == token_id]
                local_total_quantity = sum(p.quantity for p in local_positions)
                
                # 精度容差：允许0.01的差异（由于精度问题）
                balance_diff = abs(actual_balance - local_total_quantity)
                
                if balance_diff > 0.01:  # 有显著差异
                    print(f"  ⚠️  Token {token_id[:20]}... 余额不一致")
                    print(f"     本地记录: {local_total_quantity:.6f}")
                    print(f"     实际余额: {actual_balance:.6f}")
                    print(f"     差异: {balance_diff:.6f}")
                    
                    if actual_balance > local_total_quantity:
                        # 实际余额大于本地记录，说明有新的买入未记录
                        # 这种情况应该在交易时已经记录，但为了安全，我们更新数量
                        if local_positions:
                            # 更新第一个持仓的数量（合并到第一个）
                            pos = local_positions[0]
                            old_qty = pos.quantity
                            pos.quantity = round(actual_balance, 6)  # 使用实际余额，保留6位小数
                            # 如果数量增加，成本也需要相应调整（假设按比例）
                            if old_qty > 0:
                                pos.cost = round(pos.cost * (actual_balance / old_qty), 6)
                            print(f"     ✅ 已更新持仓数量: {old_qty:.6f} -> {actual_balance:.6f}")
                            updated_count += 1
                    elif actual_balance < local_total_quantity:
                        # 实际余额小于本地记录，可能是部分卖出
                        if local_positions:
                            # 更新第一个持仓的数量
                            pos = local_positions[0]
                            old_qty = pos.quantity
                            pos.quantity = round(actual_balance, 6)
                            # 按比例调整成本
                            if old_qty > 0 and actual_balance > 0:
                                pos.cost = round(pos.cost * (actual_balance / old_qty), 6)
                            else:
                                pos.cost = 0.0
                            print(f"     ✅ 已更新持仓数量: {old_qty:.6f} -> {actual_balance:.6f}")
                            updated_count += 1
                            
                            # 如果余额为0或接近0，标记为已关闭
                            if actual_balance < 0.0001:
                                pos.status = "closed"
                                print(f"     📌 持仓已关闭（余额为0）")
            except Exception as e:
                print(f"  ⚠️  同步Token {token_id[:20]}... 失败: {e}")
                continue
        
        if updated_count > 0:
            self.save_positions()
            print(f"✅ 已同步 {updated_count} 个持仓")
        else:
            print("✅ 所有持仓数据一致")
        print()
        
        return updated_count
    
    def check_all_positions(self) -> list[dict]:
        """检查所有持仓（每次检查前重新加载数据，确保获取最新持仓）"""
        # 重新加载数据，确保获取最新的持仓信息
        self.load_positions()
        
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
    
    def get_token_balance(self, token_id: str, wallet: str = "api", max_retries: int = 3) -> float:
        """
        获取 outcome token 余额（带重试机制和频率限制处理）
        
        Args:
            token_id: Token ID
            wallet: "api" = API私钥钱包, "proxy" = 网页代理钱包, "both" = 两者之和
            max_retries: 最大重试次数
        """
        balance_abi = '[{"inputs": [{"name": "account", "type": "address"}, {"name": "id", "type": "uint256"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]'
        
        def is_rate_limit_error(error) -> bool:
            """检查是否是频率限制错误"""
            error_str = str(error)
            error_lower = error_str.lower()
            
            # 检查错误消息中的关键词
            if 'rate limit' in error_lower or 'too many requests' in error_lower:
                return True
            if 'call rate limit exhausted' in error_lower:
                return True
            if 'retry in' in error_lower and ('10m' in error_lower or 'min' in error_lower):
                return True
            
            # 检查是否是字典格式的错误（从异常对象中提取）
            if isinstance(error, dict):
                if error.get('code') == -32090:
                    return True
                if error.get('message', '').lower() in ['too many requests', 'rate limit']:
                    return True
            
            # 检查异常对象的属性
            if hasattr(error, 'args') and error.args:
                for arg in error.args:
                    if isinstance(arg, dict) and arg.get('code') == -32090:
                        return True
                    arg_str = str(arg).lower()
                    if 'rate limit' in arg_str or 'too many requests' in arg_str:
                        return True
            
            return False
        
        def get_retry_delay(attempt: int) -> float:
            """计算重试延迟（指数退避）"""
            return min(2 ** attempt, 60)  # 最多等待60秒
        
        for attempt in range(max_retries):
            try:
                # 在请求之间添加延迟，减少频率限制风险
                if attempt > 0:
                    delay = get_retry_delay(attempt)
                    print(f"⏳ 等待 {delay:.1f} 秒后重试获取余额（尝试 {attempt + 1}/{max_retries}）...")
                    time.sleep(delay)
                
                ctf = self.polymarket.web3.eth.contract(address=self.polymarket.ctf_address, abi=balance_abi)
                
                api_balance = 0.0
                proxy_balance = 0.0
                
                # API 钱包余额
                if wallet in ("api", "both"):
                    api_addr = self.polymarket.client.get_address()
                    api_balance = ctf.functions.balanceOf(api_addr, int(token_id)).call() / 1e6
                    # 在请求之间添加小延迟
                    time.sleep(0.2)
                
                # 代理钱包余额
                if wallet in ("proxy", "both"):
                    proxy_addr = os.getenv("POLYMARKET_PROXY_WALLET")
                    if proxy_addr:
                        proxy_balance = ctf.functions.balanceOf(proxy_addr, int(token_id)).call() / 1e6
                        time.sleep(0.2)
                
                if wallet == "api":
                    return api_balance
                elif wallet == "proxy":
                    return proxy_balance
                else:
                    return api_balance + proxy_balance
                    
            except Exception as e:
                # 检查是否是频率限制错误
                if is_rate_limit_error(e):
                    error_str = str(e)
                    
                    # 尝试从错误消息中提取重试时间信息
                    retry_info = "10分钟"
                    if 'retry in' in error_str.lower():
                        import re
                        match = re.search(r'retry in (\d+[mh]?\d*[ms]?)', error_str.lower())
                        if match:
                            retry_info = match.group(1)
                    
                    # 尝试从异常对象中提取更详细的信息
                    error_msg = error_str
                    if hasattr(e, 'args') and e.args:
                        # 检查异常参数中是否有字典格式的错误信息
                        for arg in e.args:
                            if isinstance(arg, dict):
                                if 'message' in arg:
                                    error_msg = arg['message']
                                if 'data' in arg and isinstance(arg['data'], dict):
                                    if 'retry_in' in arg['data']:
                                        retry_info = arg['data']['retry_in']
                    
                    if attempt < max_retries - 1:
                        print(f"⚠️ 遇到频率限制: {error_msg}")
                        delay = get_retry_delay(attempt + 1)
                        print(f"   将在 {delay:.0f} 秒后重试（尝试 {attempt + 2}/{max_retries}）...")
                        continue
                    else:
                        print(f"❌ 频率限制错误（已重试 {max_retries} 次）: {error_msg}")
                        print(f"   💡 建议: 请等待约 {retry_info} 后再试，或减少请求频率")
                        print(f"   💡 你可以：")
                        print(f"      1. 等待一段时间后重试")
                        print(f"      2. 减少监控检查频率（增加检查间隔）")
                        print(f"      3. 使用本地持仓数据而不是实时查询区块链")
                        return 0.0
                else:
                    # 其他错误，只在最后一次尝试时打印
                    if attempt == max_retries - 1:
                        print(f"⚠️ 无法获取 token 余额: {e}")
                        return 0.0
                    # 非频率限制错误也等待后重试（可能也是临时错误）
                    delay = get_retry_delay(attempt + 1)
                    print(f"⏳ 遇到错误，等待 {delay:.1f} 秒后重试（尝试 {attempt + 2}/{max_retries}）...")
                    time.sleep(delay)
        
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
        
        # 验证和调整价格：Polymarket CLOB API要求价格必须在0.001-0.999之间
        # 这是API接口本身的限制，不是我们的限制
        # ⚠️ 重要：如果价格是1.0，必须调整为0.999（会损失0.001的价值）
        # 解决方案：优先使用订单簿的实际bid价格（如果存在），否则使用0.999
        sell_price = current_price
        
        # 如果价格接近1.0，尝试从订单簿获取更准确的价格
        if sell_price >= 0.99:
            print(f"   ⚠️ 价格接近1.0 ({current_price:.4f})，检查订单簿获取更准确价格...")
            try:
                orderbook = self.polymarket.get_orderbook(position.token_id)
                if orderbook and orderbook.bids:
                    # 使用订单簿中的实际最高bid价格
                    best_bid = max(orderbook.bids, key=lambda x: float(x.price))
                    orderbook_price = float(best_bid.price)
                    if orderbook_price < 1.0 and orderbook_price >= 0.001:
                        sell_price = orderbook_price
                        print(f"   ✅ 使用订单簿价格: ${sell_price:.4f} (原价格: ${current_price:.4f})")
                    elif orderbook_price >= 1.0:
                        # 订单簿价格也是1.0，必须使用0.999
                        sell_price = 0.999
                        loss = (1.0 - 0.999) * sell_quantity
                        print(f"   ⚠️ 订单簿价格也是1.0，调整为0.999 (损失: ${loss:.4f})")
            except Exception as e:
                # 订单簿不存在或其他错误，如果价格是1.0，直接使用0.999
                print(f"   ⚠️ 无法从订单簿获取价格: {e}")
                if sell_price >= 1.0:
                    sell_price = 0.999
                    loss = (1.0 - 0.999) * sell_quantity
                    print(f"   ⚠️ 价格1.0调整为0.999 (API限制，预计损失: ${loss:.4f})")
        
        # 价格范围验证和调整（API要求）
        if sell_price >= 1.0:
            # 如果仍然是1.0（上述逻辑未处理），调整为0.999
            sell_price = 0.999
            loss = (current_price - 0.999) * sell_quantity
            print(f"   ⚠️ 价格调整为 0.999 (原价格 {current_price:.4f})")
            print(f"   ⚠️ 预计损失: ${loss:.4f} ({sell_quantity:.2f} shares × ${current_price - 0.999:.4f})")
        elif sell_price > 0.999:
            sell_price = 0.999  # API最大价格限制
            loss = (current_price - 0.999) * sell_quantity
            print(f"   ⚠️ 价格调整为 0.999 (原价格 {current_price:.4f})")
            print(f"   ⚠️ 预计损失: ${loss:.4f} ({sell_quantity:.2f} shares × ${current_price - 0.999:.4f})")
        elif sell_price <= 0.0:
            sell_price = 0.001  # API最小价格限制
            print(f"   ⚠️ 价格调整为 0.001 (原价格 {current_price:.4f} 低于API最小值)")
        elif sell_price < 0.001:
            sell_price = 0.001
            print(f"   ⚠️ 价格调整为 0.001 (原价格 {current_price:.4f} 低于API最小值)")
        
        # 真实卖出（使用调整后的价格）
        try:
            result = self.polymarket.execute_order(
                price=sell_price,
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
            error_str = str(e)
            print(f"   ❌ 卖出失败: {e}")
            
            # 检查是否是订单簿不存在的错误
            if "orderbook" in error_str.lower() and "does not exist" in error_str.lower():
                error_msg = "订单簿不存在，无法通过API卖出。市场可能已关闭或结算。请等待市场结算后在Polymarket网页上手动处理，或联系Polymarket支持。"
                print(f"   💡 提示: {error_msg}")
                return {"status": "error", "reason": error_msg}
            elif "orderbook" in error_str.lower() and "404" in error_str:
                error_msg = "订单簿不存在（404）。市场可能已关闭或结算，无法通过API卖出。请等待结算后手动处理。"
                print(f"   💡 提示: {error_msg}")
                return {"status": "error", "reason": error_msg}
            else:
                return {"status": "error", "reason": str(e)}
    
    def display_positions(self):
        """显示所有持仓（先重新加载数据）"""
        # 重新加载数据，确保显示最新持仓
        self.load_positions()
        
        print()
        print("=" * 80)
        print("📊 当前持仓")
        print("=" * 80)
        
        open_positions = [p for p in self.positions if p.status == "open"]
        closed_positions = [p for p in self.positions if p.status == "closed"]
        total_positions = len(self.positions)
        
        print(f"总持仓数: {total_positions} (开放: {len(open_positions)}, 已关闭: {len(closed_positions)})")
        
        if not open_positions:
            print("没有开放持仓")
            if closed_positions:
                print(f"已关闭持仓: {len(closed_positions)} 个")
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
        # 使用默认配置（从环境变量读取）
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
        
        # 同步所有持仓的止盈止损价格（先重新加载最新数据）
        self.load_positions()
        self.sync_stop_loss_take_profit()
        
        try:
            check_count = 0
            while True:
                check_count += 1
                
                # 每次检查前从区块链同步实际持仓数据（每10次检查同步一次，避免过于频繁）
                if check_count == 1 or check_count % 10 == 0:
                    self.sync_positions_from_blockchain()
                
                # 每次检查前重新加载数据，确保获取最新持仓（check_all_positions内部也会加载）
                results = self.check_all_positions()
                
                print()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check #{check_count}")
                
                # 表格分隔线 - Shares前置，缩短Ask/Cost和Bid/Value，突出P&L
                sep = "+----------+------------------------------+------+------------+----------+----------+----------+"
                print(sep)
                print(f"| {'OrderID':<8} | {'Market':<28} | {'Side':<4} | {'Shares':>10} | {'Ask/Cost':>8} | {'Bid/Value':>8} | {'P&L':>9} |")
                print(sep)
                
                total_cost = 0
                total_value = 0
                
                for r in results:
                    question = r['question'][:25] + "..." if len(r['question']) > 28 else r['question']
                    pnl_pct = r['pnl_pct'] * 100
                    
                    # 计算value：购买的shares × 当前市场的bid价格
                    # r['current_price'] 是从订单簿API获取的bid价格（best bid，卖出价）
                    # r['quantity'] 是从区块链API获取的实际持仓数量（shares）
                    current_value = r['current_price'] * r['quantity']
                    
                    cost = r['cost']
                    order_id = r.get('order_id', '')[:8] if r.get('order_id') else '-'
                    shares = r['quantity']  # 购买的份额
                    
                    total_cost += cost
                    total_value += current_value
                    
                    ask_price = r['buy_price']  # Ask价格（买入时使用的价格）
                    bid_price = r['current_price']  # Bid价格（当前卖出价）
                    shares_str = f"{shares:.6f}"  # 购买的份额
                    # Ask/Cost 合并：缩短显示，去掉$符号，格式 "0.50/1.00"
                    ask_cost_str = f"{ask_price:.2f}/{cost:.2f}"
                    # Bid/Value 合并：缩短显示，格式 "0.55/1.10"
                    bid_value_str = f"{bid_price:.2f}/{current_value:.2f}"
                    # P&L 突出显示，使用更大的宽度
                    pnl_str = f"{pnl_pct:+.1f}%"
                    
                    print(f"| {order_id:<8} | {question:<28} | {r['side']:<4} | {shares_str:>10} | {ask_cost_str:>8} | {bid_value_str:>8} | {pnl_str:>9} |")
                    
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
                # 总计行：显示总成本、总价值和总P&L
                print(f"| {'TOTAL':<8} | {'':<28} | {'':<4} | {'':<10} | {f'{total_cost:.2f}':>8} | {f'{total_value:.2f}':>8} | {f'{total_pnl_pct:+.1f}%':>9} |")
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
