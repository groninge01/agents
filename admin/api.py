"""
管理后台 API
- 提供用户名密码认证
- 支持自动下单
- 支持实时查看监控日志
"""

import os
import sys
import json
import time
import threading
import subprocess
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, status, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
import secrets
import uvicorn

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.python.batch_trade import execute_batch_trades
from scripts.python.buy_solana_up_down import poll_and_buy_solana

def execute_batch_sell(dry_run=True, num_positions=5):
    """批量卖出持仓"""
    from scripts.python.position_monitor import PositionManager
    
    print("=" * 70)
    print("📤 批量卖出脚本")
    print("=" * 70)
    print(f"📊 卖出数量: {num_positions}")
    print(f"🔒 模式: {'模拟运行' if dry_run else '⚠️ 真实交易'}")
    print("=" * 70)
    
    pm = PositionManager()
    # 强制重新加载最新数据
    pm.load_positions()
    positions = pm.positions
    
    if not positions:
        print("\n❌ 没有持仓可卖出")
        return
    
    # 只选择开放的持仓
    open_positions = [p for p in positions if p.status == "open"]
    
    if not open_positions:
        print("\n❌ 没有开放的持仓")
        return
    
    print(f"\n📋 当前共有 {len(open_positions)} 个开放持仓（已重新加载最新数据）")
    
    # 限制卖出数量
    sell_positions = open_positions[:num_positions]
    
    print(f"\n🚀 准备卖出 {len(sell_positions)} 个持仓...")
    print("=" * 70)
    
    successful_sells = []
    for i, position in enumerate(sell_positions, 1):
        print(f"\n卖出 {i}/{len(sell_positions)}: {position.market_question[:40]}...")
        result = pm.execute_sell(position, reason="批量卖出", execute=not dry_run)
        
        if result.get("status") in ["success", "simulated"]:
            successful_sells.append({
                'question': position.market_question,
                'pnl': result.get('pnl', 0)
            })
    
    print("\n" + "=" * 70)
    print(f"✅ 批量卖出完成！成功: {len(successful_sells)}/{len(sell_positions)}")
    print("=" * 70)
    
    if successful_sells:
        total_pnl = sum(s['pnl'] for s in successful_sells)
        print(f"\n💰 总盈亏: ${total_pnl:+.2f}")
    
    return successful_sells

# ============================================================
# 配置
# ============================================================

# 认证配置 - 可以修改这些值
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 请修改为强密码！

# 日志文件路径
LOGS_DIR = PROJECT_ROOT / "logs"
MONITOR_LOG_FILE = LOGS_DIR / "monitor.log"
BATCH_TRADE_LOG_FILE = LOGS_DIR / "batch_trade.log"

# 确保日志目录存在
LOGS_DIR.mkdir(exist_ok=True)

# 安全配置
security = HTTPBasic()

# 存储交易任务的线程和状态
trade_tasks = {}
trade_task_lock = threading.Lock()

# 存储监控进程
monitor_process = None
monitor_process_lock = threading.Lock()

# 存储session tokens (简单实现，生产环境应使用Redis等)
active_tokens = {}
token_expiry = {}

def generate_token():
    """生成session token"""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=24)
    token_expiry[token] = expiry
    return token

def verify_token(token: str) -> bool:
    """验证token是否有效"""
    if token not in active_tokens:
        return False
    if token in token_expiry and datetime.now() > token_expiry[token]:
        # 清理过期token
        active_tokens.pop(token, None)
        token_expiry.pop(token, None)
        return False
    return True


# ============================================================
# 数据模型
# ============================================================


class TradeRequest(BaseModel):
    """交易请求"""
    num_trades: int = 3  # 下单数（最大5）
    amount_per_trade: float = 1.0  # 每单金额（最大1.0）
    trade_type: str = "buy"  # 交易类型：buy 或 sell
    dry_run: bool = False  # 是否模拟运行
    market_type: str = "auto"  # 市场类型：auto（自动选择）或 solana（Solana Up or Down）
    solana_side: str = "Yes"  # Solana 市场购买方向：Yes 或 No（仅当 market_type="solana" 时有效）


class SolanaTradeRequest(BaseModel):
    """Solana 市场交易请求"""
    amount: float = 1.0  # 购买金额（最大1.0）
    side: str = "Yes"  # 购买方向：Yes 或 No
    dry_run: bool = False  # 是否模拟运行


class TradeStatus(BaseModel):
    """交易状态"""
    task_id: str
    status: str  # pending, running, completed, failed
    message: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    progress: Optional[str] = None


# ============================================================
# 认证
# ============================================================


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """验证用户名密码"""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ============================================================
# FastAPI 应用
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("=" * 70)
    print("🚀 管理后台启动")
    print("=" * 70)
    print(f"📁 日志目录: {LOGS_DIR}")
    print(f"🔒 仅允许 localhost 访问")
    print(f"⚠️  注意：当前已关闭用户认证")
    print("=" * 70)
    yield
    # 关闭时清理


app = FastAPI(
    title="Polymarket 交易管理后台",
    description="批量交易和监控日志管理",
    lifespan=lifespan
)

# 仅允许 localhost 访问
@app.middleware("http")
async def localhost_only_middleware(request: Request, call_next):
    """只允许localhost访问"""
    client_host = request.client.host if request.client else None
    
    # 允许的IP地址
    allowed_hosts = ("127.0.0.1", "localhost", "::1")
    
    if client_host not in allowed_hosts:
        return JSONResponse(
            status_code=403,
            content={"detail": "仅允许从 localhost 访问"}
        )
    return await call_next(request)


# ============================================================
# 异常处理
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误（422）"""
    errors = []
    for error in exc.errors():
        # Get field path (skip 'body' prefix)
        loc = error.get("loc", [])
        field_path = " -> ".join(str(loc_item) for loc_item in loc if loc_item != "body")
        if not field_path:
            field_path = "request body"
        
        errors.append({
            "loc": list(loc),  # Keep original format for compatibility
            "field": field_path,
            "msg": error.get("msg", "Validation error"),
            "message": error.get("msg", "Validation error"),
            "type": error.get("type", "value_error")
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": errors,
            "message": f"Request validation failed. Please check {len(errors)} field(s)."
        }
    )


# ============================================================
# 路由
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def root():
    """首页 - 返回管理界面"""
    html_file = Path(__file__).parent / "ui.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("管理界面文件未找到")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/auth/login")
async def login(credentials: HTTPBasicCredentials = Depends(security)):
    """登录并获取token"""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    token = generate_token()
    active_tokens[token] = credentials.username
    
    return {
        "token": token,
        "expires_in": 86400  # 24小时
    }


@app.post("/api/trade/execute")
async def execute_trade(
    request: TradeRequest
):
    """执行批量交易"""
    
    # 验证参数
    if request.num_trades <= 0 or request.num_trades > 5:
        raise HTTPException(status_code=400, detail="交易数量必须在 1-5 之间")
    
    if request.amount_per_trade <= 0 or request.amount_per_trade > 1.0:
        raise HTTPException(status_code=400, detail="每单金额必须在 0.01-1.0 之间")
    
    if request.trade_type not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="交易类型必须是 buy 或 sell")
    
    # 生成任务ID
    task_id = f"trade_{int(time.time())}"
    
    # 创建日志文件
    log_file = LOGS_DIR / f"batch_trade_{task_id}.log"
    
    def run_trade():
        """在后台线程中运行交易"""
        with trade_task_lock:
            trade_tasks[task_id] = {
                "status": "running",
                "message": "交易执行中...",
                "start_time": datetime.now().isoformat(),
                "log_file": str(log_file)
            }
        
        try:
            # 重定向输出到日志文件
            import sys
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            
            # 使用追加模式打开日志文件，并立即刷新
            with open(log_file, "w", encoding="utf-8") as f:
                # 创建一个自定义的文件对象，每次写入后立即刷新
                class FlushFile:
                    def __init__(self, file):
                        self.file = file
                    def write(self, s):
                        self.file.write(s)
                        self.file.flush()
                        os.fsync(self.file.fileno())
                    def flush(self):
                        self.file.flush()
                        os.fsync(self.file.fileno())
                    def __getattr__(self, name):
                        return getattr(self.file, name)
                
                flush_file = FlushFile(f)
                sys.stdout = flush_file
                sys.stderr = flush_file
                
                try:
                    print(f"[{datetime.now().isoformat()}] Starting trade execution...")
                    print(f"[{datetime.now().isoformat()}] Trade type: {request.trade_type}, Dry run: {request.dry_run}")
                    flush_file.flush()
                    
                    if request.trade_type == "buy":
                        # 检查市场类型
                        if request.market_type == "solana":
                            # Solana Up or Down 市场购买
                            print(f"[{datetime.now().isoformat()}] Market type: Solana Up or Down")
                            print(f"[{datetime.now().isoformat()}] Solana side: {request.solana_side}")
                            print(f"[{datetime.now().isoformat()}] Calling poll_and_buy_solana...")
                            flush_file.flush()
                            
                            from agents.polymarket.gamma import GammaMarketClient
                            from agents.polymarket.polymarket import Polymarket
                            
                            gamma = GammaMarketClient()
                            polymarket = Polymarket()
                            
                            # 对于 Solana 市场，num_trades 表示轮询次数（最多等待15分钟）
                            # amount_per_trade 是每次购买的金额
                            max_wait_minutes = min(request.num_trades * 3, 15)  # 每个交易最多等待3分钟，总最多15分钟
                            
                            result = poll_and_buy_solana(
                                gamma=gamma,
                                polymarket=polymarket,
                                amount=request.amount_per_trade,
                                side=request.solana_side,
                                dry_run=request.dry_run,
                                max_wait_minutes=max_wait_minutes
                            )
                            
                            if result:
                                print(f"[{datetime.now().isoformat()}] ✅ Solana market purchase completed successfully")
                            else:
                                print(f"[{datetime.now().isoformat()}] ⚠️ Solana market purchase completed but no trade executed (market may not have opened)")
                            
                            print(f"[{datetime.now().isoformat()}] poll_and_buy_solana completed")
                        else:
                            # 自动选择市场
                            print(f"[{datetime.now().isoformat()}] Market type: Auto-select")
                            print(f"[{datetime.now().isoformat()}] Calling execute_batch_trades...")
                            flush_file.flush()
                            execute_batch_trades(
                                dry_run=request.dry_run,
                                amount_per_trade=request.amount_per_trade,
                                num_trades=request.num_trades
                            )
                            print(f"[{datetime.now().isoformat()}] execute_batch_trades completed")
                    else:
                        # 卖出功能：卖出已有持仓
                        print(f"[{datetime.now().isoformat()}] Calling execute_batch_sell...")
                        flush_file.flush()
                        from scripts.python.position_monitor import PositionManager
                        execute_batch_sell(
                            dry_run=request.dry_run,
                            num_positions=request.num_trades
                        )
                        print(f"[{datetime.now().isoformat()}] execute_batch_sell completed")
                    
                    print(f"[{datetime.now().isoformat()}] Trade execution completed successfully")
                    flush_file.flush()
                    
                    with trade_task_lock:
                        trade_tasks[task_id]["status"] = "completed"
                        trade_tasks[task_id]["message"] = "交易完成"
                        trade_tasks[task_id]["end_time"] = datetime.now().isoformat()
                        
                except Exception as e:
                    error_msg = f"❌ 交易执行失败: {e}"
                    print(error_msg)
                    import traceback
                    traceback.print_exc()
                    flush_file.flush()
                    
                    with trade_task_lock:
                        trade_tasks[task_id]["status"] = "failed"
                        trade_tasks[task_id]["message"] = f"交易失败: {str(e)}"
                        trade_tasks[task_id]["end_time"] = datetime.now().isoformat()
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    
        except Exception as e:
            with trade_task_lock:
                trade_tasks[task_id]["status"] = "failed"
                trade_tasks[task_id]["message"] = f"执行异常: {str(e)}"
                trade_tasks[task_id]["end_time"] = datetime.now().isoformat()
    
    # 启动后台线程
    thread = threading.Thread(target=run_trade, daemon=True)
    thread.start()
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "交易任务已启动",
        "num_trades": request.num_trades,
        "amount_per_trade": request.amount_per_trade,
        "trade_type": request.trade_type,
        "dry_run": request.dry_run
    }


@app.get("/api/trade/status/{task_id}")
async def get_trade_status(
    task_id: str
):
    """获取交易状态"""
    with trade_task_lock:
        task = trade_tasks.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "message": task["message"],
        "start_time": task.get("start_time"),
        "end_time": task.get("end_time"),
        "log_file": task.get("log_file")
    }


@app.get("/api/trade/list")
async def list_trades():
    """列出所有交易任务"""
    with trade_task_lock:
        tasks = []
        for task_id, task in trade_tasks.items():
            tasks.append({
                "task_id": task_id,
                "status": task["status"],
                "message": task["message"],
                "start_time": task.get("start_time"),
                "end_time": task.get("end_time")
            })
    
    # 按时间倒序排列
    tasks.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return {"tasks": tasks}


@app.get("/api/logs/monitor")
async def stream_monitor_logs():
    """实时流式传输监控日志"""
    
    def generate():
        """生成日志流"""
        # 如果日志文件不存在，创建一个空文件
        if not MONITOR_LOG_FILE.exists():
            MONITOR_LOG_FILE.touch()
        
        # 初始化文件位置
        file_position = 0
        
        # 先发送已有的内容（只发送最后100行）
        try:
            if MONITOR_LOG_FILE.exists() and MONITOR_LOG_FILE.stat().st_size > 0:
                with open(MONITOR_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                    # 只发送最后100行
                    lines_to_send = all_lines[-100:] if len(all_lines) > 100 else all_lines
                    for line in lines_to_send:
                        if line.strip():  # 跳过空行
                            yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                # 更新文件位置到文件末尾（使用文件大小）
                file_position = MONITOR_LOG_FILE.stat().st_size
        except Exception as e:
            # 如果读取失败，从头开始
            file_position = 0
        
        # 发送心跳保持连接
        last_heartbeat = time.time()
        
        # 持续监控新内容
        while True:
            try:
                # 检查文件是否存在
                if not MONITOR_LOG_FILE.exists():
                    time.sleep(1)
                    continue
                
                # 获取当前文件大小
                current_size = MONITOR_LOG_FILE.stat().st_size
                
                # 如果文件被截断或重置，从头开始
                if current_size < file_position:
                    file_position = 0
                
                # 如果有新内容
                if current_size > file_position:
                    try:
                        with open(MONITOR_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            f.seek(file_position)
                            # 读取新内容
                            new_content = f.read(current_size - file_position)
                            
                            if new_content:
                                # 按行分割
                                lines = new_content.splitlines(keepends=False)
                                
                                # 发送所有完整的行
                                for line in lines:
                                    if line.strip():
                                        yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                                
                                # 更新文件位置到当前大小
                                file_position = current_size
                    except Exception as e:
                        # 读取失败，等待下次重试
                        pass
                
                # 发送心跳（每30秒）
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    yield f": heartbeat\n\n"
                    last_heartbeat = current_time
                
                time.sleep(0.3)  # 每0.3秒检查一次，提高响应速度
                
            except Exception as e:
                yield f"data: {json.dumps({'error': f'读取日志错误: {str(e)}'})}\n\n"
                time.sleep(1)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用nginx缓冲
        }
    )


@app.get("/api/logs/trade/{task_id}")
async def stream_trade_logs(
    task_id: str
):
    """实时流式传输交易日志"""
    
    # 获取任务日志文件路径
    with trade_task_lock:
        task = trade_tasks.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    log_file = Path(task.get("log_file", ""))
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")
    
    def generate():
        """生成日志流"""
        file_position = 0
        
        # 先发送已有内容
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                file_position = f.tell()
        except:
            pass
        
        # 监控新内容（如果任务还在运行）
        max_wait_time = 300  # 最多等待5分钟
        wait_count = 0
        
        while wait_count < max_wait_time:
            try:
                current_size = log_file.stat().st_size
                
                if current_size > file_position:
                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(file_position)
                        new_lines = f.readlines()
                        
                        if new_lines:
                            file_position = f.tell()
                            for line in new_lines:
                                yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                
                # 检查任务是否完成
                with trade_task_lock:
                    task_status = trade_tasks.get(task_id, {}).get("status")
                
                if task_status in ("completed", "failed"):
                    # 读取剩余内容
                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(file_position)
                        remaining_lines = f.readlines()
                        for line in remaining_lines:
                            yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                    break
                
                time.sleep(0.5)
                wait_count += 0.5
                
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(1)
                wait_count += 1
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/logs/monitor/history")
async def get_monitor_log_history(
    lines: int = 100
):
    """获取监控日志历史（最后N行）"""
    if not MONITOR_LOG_FILE.exists():
        return {"lines": []}
    
    try:
        with open(MONITOR_LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            # 返回最后N行
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {
                "lines": [line.rstrip() for line in last_lines],
                "total_lines": len(all_lines)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")


@app.get("/api/monitor/config")
async def get_monitor_config():
    """获取监控配置参数"""
    from scripts.python.position_monitor import (
        TAKE_PROFIT_PCT, 
        STOP_LOSS_PCT, 
        MONITOR_INTERVAL, 
        AUTO_EXECUTE
    )
    
    return {
        "take_profit_pct": TAKE_PROFIT_PCT,
        "stop_loss_pct": STOP_LOSS_PCT,
        "monitor_interval": MONITOR_INTERVAL,
        "auto_execute": AUTO_EXECUTE
    }


@app.get("/api/positions")
async def get_positions():
    """
    获取当前持仓数据（从接口获取）
    返回市场名称、持仓数量（shares）和当前价值（value）
    """
    try:
        from scripts.python.position_monitor import PositionManager
        
        pm = PositionManager()
        pm.load_positions()
        
        open_positions = [p for p in pm.positions if p.status == "open"]
        
        if not open_positions:
            return {
                "positions": [],
                "total_value": 0.0,
                "count": 0
            }
        
        positions_data = []
        total_value = 0.0
        
        for position in open_positions:
            # 从区块链接口获取实际持仓数量（购买的shares）
            try:
                actual_shares = pm.get_token_balance(position.token_id, wallet="both")
                if actual_shares > 0.0001:
                    shares = round(actual_shares, 6)
                else:
                    shares = position.quantity
            except:
                shares = position.quantity
            
            # 从订单簿接口获取当前市场的bid价格（卖出价）
            bid_price = pm.get_current_price(position.token_id)  # 返回的是best bid价格
            if bid_price is None:
                bid_price = position.buy_price  # 如果无法获取，使用买入价作为备用
            
            # 计算value：购买的shares × 当前市场的bid价格
            value = round(shares * bid_price, 6)
            total_value += value
            
            position_info = {
                "market": position.market_question,
                "shares": round(shares, 6),  # 持仓数量（购买的shares，从区块链接口获取）
                "value": round(value, 2)  # 当前价值 = shares × bid_price（保留2位小数）
            }
            
            positions_data.append(position_info)
        
        return {
            "positions": positions_data,
            "total_value": round(total_value, 2),
            "count": len(positions_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓数据失败: {str(e)}")


class SellRequest(BaseModel):
    token_id: str
    shares: float
    reason: str = "手动卖出"


@app.get("/api/positions/sellable")
async def get_sellable_positions():
    """
    获取可卖出持仓列表（详细信息）
    用于卖出页面显示
    """
    try:
        from scripts.python.position_monitor import PositionManager
        
        pm = PositionManager()
        pm.load_positions()
        
        open_positions = [p for p in pm.positions if p.status == "open"]
        
        if not open_positions:
            return {
                "positions": [],
                "total_value": 0.0,
                "count": 0
            }
        
        positions_data = []
        total_value = 0.0
        
        for position in open_positions:
            # 从区块链接口获取实际持仓数量（购买的shares）
            try:
                actual_shares = pm.get_token_balance(position.token_id, wallet="both")
                if actual_shares > 0.0001:
                    shares = round(actual_shares, 6)
                else:
                    shares = position.quantity
            except:
                shares = position.quantity
            
            # 从订单簿接口获取当前市场的bid价格（卖出价）
            bid_price = pm.get_current_price(position.token_id)
            if bid_price is None:
                bid_price = position.buy_price
            
            # 计算value和盈亏
            value = round(shares * bid_price, 6)
            pnl = (bid_price - position.buy_price) * shares
            pnl_pct = ((bid_price - position.buy_price) / position.buy_price * 100) if position.buy_price > 0 else 0
            
            total_value += value
            
            position_info = {
                "token_id": position.token_id,
                "market": position.market_question,
                "side": position.side,
                "buy_price": round(position.buy_price, 4),
                "bid_price": round(bid_price, 4),
                "shares": round(shares, 6),
                "cost": round(position.cost, 2),
                "value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2)
            }
            
            positions_data.append(position_info)
        
        return {
            "positions": positions_data,
            "total_value": round(total_value, 2),
            "count": len(positions_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可卖出持仓列表失败: {str(e)}")


@app.post("/api/positions/sell")
async def sell_position(request: SellRequest):
    """
    卖出单个持仓
    """
    try:
        from scripts.python.position_monitor import PositionManager
        
        pm = PositionManager()
        pm.load_positions()
        
        # 找到对应的持仓
        position = next((p for p in pm.positions if p.token_id == request.token_id and p.status == "open"), None)
        if not position:
            raise HTTPException(status_code=404, detail="持仓未找到或已关闭")
        
        # 获取实际持仓数量
        try:
            actual_shares = pm.get_token_balance(position.token_id, wallet="both")
            if actual_shares < 0.0001:
                raise HTTPException(status_code=400, detail="持仓数量不足")
            
            # 验证卖出数量
            if request.shares <= 0:
                raise HTTPException(status_code=400, detail="卖出数量必须大于0")
            if request.shares > actual_shares + 0.0001:  # 允许小的精度差异
                raise HTTPException(status_code=400, detail=f"卖出数量不能超过持仓数量 {actual_shares:.6f}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"获取持仓数量失败: {str(e)}")
        
        # 获取当前价格
        current_price = pm.get_current_price(position.token_id)
        if current_price is None:
            raise HTTPException(status_code=400, detail="无法获取当前价格")
        
        # 检查API钱包余额，因为execute_sell只从API钱包卖出
        api_balance = pm.get_token_balance(position.token_id, wallet="api")
        proxy_balance = pm.get_token_balance(position.token_id, wallet="proxy")
        
        # 检查是否有足够的余额卖出（允许小的精度差异）
        if api_balance < request.shares * 0.99:  # 需要至少99%的请求数量
            # 如果token大部分在代理钱包中
            if proxy_balance >= actual_shares * 0.99:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Token在代理钱包中，无法通过API卖出。API钱包余额: {api_balance:.6f}, 代理钱包余额: {proxy_balance:.6f}。请在Polymarket网页上手动卖出。"
                )
            else:
                # API钱包余额不足
                raise HTTPException(
                    status_code=400, 
                    detail=f"API钱包余额不足，无法卖出。API钱包余额: {api_balance:.6f}, 代理钱包余额: {proxy_balance:.6f}, 请求卖出数量: {request.shares:.6f}。请在Polymarket网页上手动卖出或等待token转移到API钱包。"
                )
        
        # 如果卖出全部份额，使用原有的execute_sell方法
        if abs(request.shares - actual_shares) < 0.0001:
            result = pm.execute_sell(position, reason=request.reason, execute=True)
            if result.get("status") == "success":
                return {
                    "status": "success",
                    "message": "卖出成功",
                    "pnl": result.get("pnl", 0)
                }
            else:
                error_reason = result.get("reason", "卖出失败")
                raise HTTPException(
                    status_code=400, 
                    detail=f"卖出失败: {error_reason}"
                )
        else:
            # 部分卖出 - 这里需要实现部分卖出逻辑
            # 目前先返回错误，提示用户需要全部卖出
            raise HTTPException(
                status_code=400, 
                detail=f"目前只支持全部卖出。持仓数量: {actual_shares:.6f}, 请求卖出数量: {request.shares:.6f}。请选择全部份额。"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"卖出失败: {str(e)}\n详细信息请查看服务器日志。"
        )




def is_monitor_running():
    """检查监控进程是否在运行（检查系统进程）"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "start_monitor.py"],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0 and result.stdout.strip()
    except:
        return False

@app.get("/api/monitor/status")
async def get_monitor_status():
    """获取监控进程状态"""
    # 快速检查系统进程（使用更快的命令）
    try:
        # 使用更快的检查方式
        result = subprocess.run(
            ["pgrep", "-f", "start_monitor.py"],
            capture_output=True,
            timeout=1,  # 减少超时时间
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            pid = int(pids[0])
            return {
                "running": True,
                "pid": pid
            }
    except subprocess.TimeoutExpired:
        # 超时表示可能没有进程或检查太慢
        pass
    except:
        pass
    
    return {
        "running": False,
        "pid": None
    }


@app.post("/api/monitor/start")
async def start_monitor():
    """启动监控进程"""
    global monitor_process
    
    # 快速检查是否已经在运行（不阻塞）
    try:
        quick_check = subprocess.run(
            ["pgrep", "-f", "start_monitor.py"],
            capture_output=True,
            timeout=0.5  # 很短的超时
        )
        if quick_check.returncode == 0 and quick_check.stdout.strip():
            pid = int(quick_check.stdout.decode().strip().split('\n')[0])
            return {
                "status": "already_running",
                "message": f"监控进程已在运行 (PID: {pid})",
                "pid": pid
            }
    except:
        pass  # 忽略检查错误，继续启动
    
    # 在后台线程中执行启动操作，避免阻塞API
    def start_in_background():
        try:
            # 停止旧进程
            subprocess.Popen(
                ["pkill", "-f", "start_monitor.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(0.5)  # 短暂等待
            
            # 清空日志文件
            if MONITOR_LOG_FILE.exists():
                MONITOR_LOG_FILE.write_text("")
            
            # 启动新进程
            python_executable = sys.executable
            monitor_script = PROJECT_ROOT / "scripts" / "python" / "start_monitor.py"
            log_file_path = str(MONITOR_LOG_FILE)
            
            import shlex
            cmd = f"nohup {shlex.quote(python_executable)} -u {shlex.quote(str(monitor_script))} > {shlex.quote(log_file_path)} 2>&1 &"
            
            subprocess.Popen(
                cmd,
                shell=True,
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"启动监控进程时出错: {e}")
    
    # 在后台线程启动，立即返回
    thread = threading.Thread(target=start_in_background, daemon=True)
    thread.start()
    
    # 立即返回响应
    return {
        "status": "started",
        "message": "监控进程启动命令已执行，请稍后查看状态"
    }


@app.post("/api/monitor/stop")
async def stop_monitor():
    """停止监控进程"""
    global monitor_process
    
    with monitor_process_lock:
        if monitor_process is None or monitor_process.poll() is not None:
            return {
                "status": "not_running",
                "message": "监控进程未运行"
            }
        
        try:
            # 尝试优雅停止
            monitor_process.terminate()
            monitor_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # 强制停止
            monitor_process.kill()
            monitor_process.wait()
        except Exception as e:
            pass
        
        monitor_process = None
        
        # 同时停止可能遗留的进程
        try:
            subprocess.run(["pkill", "-f", "start_monitor.py"], 
                         capture_output=True, timeout=5)
        except:
            pass
        
        return {
            "status": "stopped",
            "message": "监控进程已停止"
        }


# ============================================================
# 启动服务器
# ============================================================


if __name__ == "__main__":
    # 仅监听 localhost
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8888,
        reload=False,
        log_level="info"
    )

