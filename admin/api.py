"""
Admin dashboard API
- Provides username/password authentication
- Supports automated trading
- Supports real-time monitoring log viewing
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

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.python.batch_trade import execute_batch_trades
from scripts.python.buy_solana_up_down import poll_and_buy_solana

def execute_batch_sell(dry_run=True, num_positions=5):
    """Batch-sell positions."""
    from scripts.python.position_monitor import PositionManager

    print("=" * 70)
    print("📤 Batch sell script")
    print("=" * 70)
    print(f"📊 Sell count: {num_positions}")
    print(f"🔒 Mode: {'Dry run' if dry_run else '⚠️ LIVE TRADE'}")
    print("=" * 70)

    pm = PositionManager()
    # Force reload latest data
    pm.load_positions()
    positions = pm.positions

    if not positions:
        print("\n❌ No positions to sell")
        return

    # Only select open positions
    open_positions = [p for p in positions if p.status == "open"]

    if not open_positions:
        print("\n❌ No open positions")
        return

    print(f"\n📋 Currently {len(open_positions)} open positions (latest data reloaded)")

    # Limit sell count
    sell_positions = open_positions[:num_positions]

    print(f"\n🚀 Preparing to sell {len(sell_positions)} positions...")
    print("=" * 70)

    successful_sells = []
    for i, position in enumerate(sell_positions, 1):
        print(f"\nSell {i}/{len(sell_positions)}: {position.market_question[:40]}...")
        result = pm.execute_sell(position, reason="Batch sell", execute=not dry_run)

        if result.get("status") in ["success", "simulated"]:
            successful_sells.append({
                'question': position.market_question,
                'pnl': result.get('pnl', 0)
            })

    print("\n" + "=" * 70)
    print(f"✅ Batch sell completed! Success: {len(successful_sells)}/{len(sell_positions)}")
    print("=" * 70)

    if successful_sells:
        total_pnl = sum(s['pnl'] for s in successful_sells)
        print(f"\n💰 Total PnL: ${total_pnl:+.2f}")

    return successful_sells

# ============================================================
# Configuration
# ============================================================

# Auth configuration - you can change these
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Please change to a strong password!

# Log file paths
LOGS_DIR = PROJECT_ROOT / "logs"
MONITOR_LOG_FILE = LOGS_DIR / "monitor.log"
BATCH_TRADE_LOG_FILE = LOGS_DIR / "batch_trade.log"

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

# Security configuration
security = HTTPBasic()

# Store trade task threads and status
trade_tasks = {}
trade_task_lock = threading.Lock()

# Store monitor process
monitor_process = None
monitor_process_lock = threading.Lock()

# Store session tokens (simple implementation; use Redis/etc in production)
active_tokens = {}
token_expiry = {}

def generate_token():
    """Generate a session token."""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=24)
    token_expiry[token] = expiry
    return token

def verify_token(token: str) -> bool:
    """Verify whether a token is valid."""
    if token not in active_tokens:
        return False
    if token in token_expiry and datetime.now() > token_expiry[token]:
        # Clean up expired token
        active_tokens.pop(token, None)
        token_expiry.pop(token, None)
        return False
    return True


# ============================================================
# Data models
# ============================================================


class TradeRequest(BaseModel):
    """Trade request."""
    num_trades: int = 3  # Number of trades (max 5)
    amount_per_trade: float = 1.0  # Amount per trade (max 1.0)
    trade_type: str = "buy"  # Trade type: buy or sell
    dry_run: bool = False  # Dry run
    market_type: str = "auto"  # Market type: auto (auto-select) or solana (Solana Up or Down)
    solana_side: str = "Yes"  # Solana side: Yes or No (only when market_type="solana")


class SolanaTradeRequest(BaseModel):
    """Solana market trade request."""
    amount: float = 1.0  # Amount (max 1.0)
    side: str = "Yes"  # Side: Yes or No
    dry_run: bool = False  # Dry run


class TradeStatus(BaseModel):
    """Trade status."""
    task_id: str
    status: str  # pending, running, completed, failed
    message: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    progress: Optional[str] = None


# ============================================================
# Authentication
# ============================================================


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify username/password."""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ============================================================
# FastAPI application
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan management."""
    # On startup
    print("=" * 70)
    print("🚀 Admin dashboard starting")
    print("=" * 70)
    print(f"📁 Logs directory: {LOGS_DIR}")
    print(f"🔒 Only localhost access is allowed")
    print(f"⚠️  Note: user authentication is currently disabled")
    print("=" * 70)
    yield
    # Cleanup on shutdown


app = FastAPI(
    title="Polymarket Trading Admin Dashboard",
    description="Batch trading and monitoring log management",
    lifespan=lifespan
)

# Allow only localhost access
@app.middleware("http")
async def localhost_only_middleware(request: Request, call_next):
    """Allow only localhost access."""
    client_host = request.client.host if request.client else None

    # Allowed IP addresses
    allowed_hosts = ("127.0.0.1", "localhost", "::1")

    if client_host not in allowed_hosts:
        return JSONResponse(
            status_code=403,
            content={"detail": "Only localhost access is allowed"}
        )
    return await call_next(request)


# ============================================================
# Exception handling
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors (422)."""
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
# Routes
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def root():
    """Home - return admin UI."""
    html_file = Path(__file__).parent / "ui.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("Admin UI file not found")


@app.get("/api/health")
async def health_check():
    """Health check."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/auth/login")
async def login(credentials: HTTPBasicCredentials = Depends(security)):
    """Login and get a token."""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    token = generate_token()
    active_tokens[token] = credentials.username

    return {
        "token": token,
        "expires_in": 86400  # 24 hours
    }


@app.post("/api/trade/execute")
async def execute_trade(
    request: TradeRequest
):
    """Execute batch trades."""

    # Validate parameters
    if request.num_trades <= 0 or request.num_trades > 5:
        raise HTTPException(status_code=400, detail="Number of trades must be between 1 and 5")

    if request.amount_per_trade <= 0 or request.amount_per_trade > 1.0:
        raise HTTPException(status_code=400, detail="Amount per trade must be between 0.01 and 1.0")

    if request.trade_type not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Trade type must be buy or sell")

    # Generate task ID
    task_id = f"trade_{int(time.time())}"

    # Create log file
    log_file = LOGS_DIR / f"batch_trade_{task_id}.log"

    def run_trade():
        """Run trade in a background thread."""
        with trade_task_lock:
            trade_tasks[task_id] = {
                "status": "running",
                "message": "Trade running...",
                "start_time": datetime.now().isoformat(),
                "log_file": str(log_file)
            }

        try:
            # Redirect output to log file
            import sys
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            # Open log file and flush immediately
            with open(log_file, "w", encoding="utf-8") as f:
                # Custom wrapper to flush after each write
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
                        # Check market type
                        if request.market_type == "solana":
                            # Solana Up or Down market purchase
                            print(f"[{datetime.now().isoformat()}] Market type: Solana Up or Down")
                            print(f"[{datetime.now().isoformat()}] Solana side: {request.solana_side}")
                            print(f"[{datetime.now().isoformat()}] Calling poll_and_buy_solana...")
                            flush_file.flush()

                            from agents.polymarket.gamma import GammaMarketClient
                            from agents.polymarket.polymarket import Polymarket

                            gamma = GammaMarketClient()
                            polymarket = Polymarket()

                            # For Solana market, num_trades indicates polling iterations (up to 15 minutes)
                            # amount_per_trade is the amount per purchase
                            max_wait_minutes = min(request.num_trades * 3, 15)  # Up to 3 min per trade; max 15 min total

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
                            # Auto-select market
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
                        # Sell: sell existing positions
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
                        trade_tasks[task_id]["message"] = "Trade completed"
                        trade_tasks[task_id]["end_time"] = datetime.now().isoformat()

                except Exception as e:
                    error_msg = f"❌ Trade execution failed: {e}"
                    print(error_msg)
                    import traceback
                    traceback.print_exc()
                    flush_file.flush()

                    with trade_task_lock:
                        trade_tasks[task_id]["status"] = "failed"
                        trade_tasks[task_id]["message"] = f"Trade failed: {str(e)}"
                        trade_tasks[task_id]["end_time"] = datetime.now().isoformat()
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

        except Exception as e:
            with trade_task_lock:
                trade_tasks[task_id]["status"] = "failed"
                trade_tasks[task_id]["message"] = f"Execution error: {str(e)}"
                trade_tasks[task_id]["end_time"] = datetime.now().isoformat()

    # Start background thread
    thread = threading.Thread(target=run_trade, daemon=True)
    thread.start()

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Trade task started",
        "num_trades": request.num_trades,
        "amount_per_trade": request.amount_per_trade,
        "trade_type": request.trade_type,
        "dry_run": request.dry_run
    }


@app.get("/api/trade/status/{task_id}")
async def get_trade_status(
    task_id: str
):
    """Get trade status."""
    with trade_task_lock:
        task = trade_tasks.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

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
    """List all trade tasks."""
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

    # Sort by time descending
    tasks.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return {"tasks": tasks}


@app.get("/api/logs/monitor")
async def stream_monitor_logs():
    """Stream monitor logs in real time."""

    def generate():
        """Generate log stream."""
        # If the log file does not exist, create an empty file
        if not MONITOR_LOG_FILE.exists():
            MONITOR_LOG_FILE.touch()

        # Initialize file position
        file_position = 0

        # Send existing content first (only the last 100 lines)
        try:
            if MONITOR_LOG_FILE.exists() and MONITOR_LOG_FILE.stat().st_size > 0:
                with open(MONITOR_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                    # Only send last 100 lines
                    lines_to_send = all_lines[-100:] if len(all_lines) > 100 else all_lines
                    for line in lines_to_send:
                        if line.strip():  # Skip empty lines
                            yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                # Update file position to end of file (use file size)
                file_position = MONITOR_LOG_FILE.stat().st_size
        except Exception as e:
            # If reading fails, start from the beginning
            file_position = 0

        # Send heartbeat to keep connection alive
        last_heartbeat = time.time()

        # Continuously monitor new content
        while True:
            try:
                # Check whether file exists
                if not MONITOR_LOG_FILE.exists():
                    time.sleep(1)
                    continue

                # Get current file size
                current_size = MONITOR_LOG_FILE.stat().st_size

                # If file was truncated/reset, start over
                if current_size < file_position:
                    file_position = 0

                # If there is new content
                if current_size > file_position:
                    try:
                        with open(MONITOR_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            f.seek(file_position)
                            # Read new content
                            new_content = f.read(current_size - file_position)

                            if new_content:
                                # Split into lines
                                lines = new_content.splitlines(keepends=False)

                                # Send all complete lines
                                for line in lines:
                                    if line.strip():
                                        yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"

                                # Update file position to current size
                                file_position = current_size
                    except Exception as e:
                        # Read failed; retry next time
                        pass

                # Heartbeat (every 30 seconds)
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    yield f": heartbeat\n\n"
                    last_heartbeat = current_time

                time.sleep(0.3)  # Check every 0.3s for responsiveness

            except Exception as e:
                yield f"data: {json.dumps({'error': f'Log read error: {str(e)}'})}\n\n"
                time.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/api/logs/trade/{task_id}")
async def stream_trade_logs(
    task_id: str
):
    """Stream trade logs in real time."""

    # Get task log file path
    with trade_task_lock:
        task = trade_tasks.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    log_file = Path(task.get("log_file", ""))
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    def generate():
        """Generate log stream."""
        file_position = 0

        # Send existing content first
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                file_position = f.tell()
        except:
            pass

        # Monitor new content (while task is still running)
        max_wait_time = 300  # Max wait 5 minutes
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

                # Check whether task is completed
                with trade_task_lock:
                    task_status = trade_tasks.get(task_id, {}).get("status")

                if task_status in ("completed", "failed"):
                    # Read remaining content
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
    """Get monitor log history (last N lines)."""
    if not MONITOR_LOG_FILE.exists():
        return {"lines": []}

    try:
        with open(MONITOR_LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            # Return last N lines
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {
                "lines": [line.rstrip() for line in last_lines],
                "total_lines": len(all_lines)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {str(e)}")


@app.get("/api/monitor/config")
async def get_monitor_config():
    """Get monitor configuration parameters."""
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
    Get current position data (from APIs).
    Returns market name, shares, and current value.
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
            # Get actual shares from blockchain API
            try:
                actual_shares = pm.get_token_balance(position.token_id, wallet="both")
                if actual_shares > 0.0001:
                    shares = round(actual_shares, 6)
                else:
                    shares = position.quantity
            except:
                shares = position.quantity

            # Get current market bid price from order book API (sell price)
            bid_price = pm.get_current_price(position.token_id)  # Returns best bid
            if bid_price is None:
                bid_price = position.buy_price  # Fallback to entry price

            # Value = shares × bid_price
            value = round(shares * bid_price, 6)
            total_value += value

            position_info = {
                "market": position.market_question,
                "shares": round(shares, 6),  # Shares
                "value": round(value, 2)  # Current value = shares × bid_price (2 decimals)
            }

            positions_data.append(position_info)

        return {
            "positions": positions_data,
            "total_value": round(total_value, 2),
            "count": len(positions_data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch position data: {str(e)}")


class SellRequest(BaseModel):
    token_id: str
    shares: float
    reason: str = "Manual sell"


@app.get("/api/positions/sellable")
async def get_sellable_positions():
    """
    Get sellable positions list (detailed).
    Used for the sell UI.
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
            # Get actual shares from blockchain API
            try:
                actual_shares = pm.get_token_balance(position.token_id, wallet="both")
                if actual_shares > 0.0001:
                    shares = round(actual_shares, 6)
                else:
                    shares = position.quantity
            except:
                shares = position.quantity

            # Get current market bid price (sell price)
            bid_price = pm.get_current_price(position.token_id)
            if bid_price is None:
                bid_price = position.buy_price

            # Compute value and PnL
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
        raise HTTPException(status_code=500, detail=f"Failed to fetch sellable positions: {str(e)}")


@app.post("/api/positions/sell")
async def sell_position(request: SellRequest):
    """
    Sell a single position.
    """
    try:
        from scripts.python.position_monitor import PositionManager

        pm = PositionManager()
        pm.load_positions()

        # Find the matching position
        position = next((p for p in pm.positions if p.token_id == request.token_id and p.status == "open"), None)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found or already closed")

        # Get actual shares
        try:
            actual_shares = pm.get_token_balance(position.token_id, wallet="both")
            if actual_shares < 0.0001:
                raise HTTPException(status_code=400, detail="Insufficient position size")

            # Validate sell size
            if request.shares <= 0:
                raise HTTPException(status_code=400, detail="Sell size must be greater than 0")
            if request.shares > actual_shares + 0.0001:  # Allow small precision difference
                raise HTTPException(status_code=400, detail=f"Sell size cannot exceed position size {actual_shares:.6f}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch position size: {str(e)}")

        # Get current price
        current_price = pm.get_current_price(position.token_id)
        if current_price is None:
            raise HTTPException(status_code=400, detail="Unable to fetch current price")

        # Check API wallet balance because execute_sell sells only from API wallet
        api_balance = pm.get_token_balance(position.token_id, wallet="api")
        proxy_balance = pm.get_token_balance(position.token_id, wallet="proxy")

        # Check whether balance is sufficient to sell (allow small precision difference)
        if api_balance < request.shares * 0.99:  # Need at least 99% of requested amount
            # If token is mostly in proxy wallet
            if proxy_balance >= actual_shares * 0.99:
                raise HTTPException(
                    status_code=400,
                    detail=f"Token is in proxy wallet; cannot sell via API. API wallet balance: {api_balance:.6f}, proxy wallet balance: {proxy_balance:.6f}. Please sell in the Polymarket web UI."
                )
            else:
                # API wallet balance is insufficient
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient API wallet balance to sell. API wallet balance: {api_balance:.6f}, proxy wallet balance: {proxy_balance:.6f}, requested sell size: {request.shares:.6f}. Please sell in the Polymarket web UI or wait for token transfer to the API wallet."
                )

        # If selling full size, use existing execute_sell
        if abs(request.shares - actual_shares) < 0.0001:
            result = pm.execute_sell(position, reason=request.reason, execute=True)
            if result.get("status") == "success":
                return {
                    "status": "success",
                    "message": "Sell successful",
                    "pnl": result.get("pnl", 0)
                }
            else:
                error_reason = result.get("reason", "Sell failed")
                raise HTTPException(
                    status_code=400,
                    detail=f"Sell failed: {error_reason}"
                )
        else:
            # Partial sell - not implemented yet
            raise HTTPException(
                status_code=400,
                detail=f"Currently only full sells are supported. Position size: {actual_shares:.6f}, requested sell size: {request.shares:.6f}. Please select all shares."
            )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Sell failed: {str(e)}\nPlease check server logs for details."
        )


def is_monitor_running():
    """Check whether monitor process is running (via system processes)."""
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
    """Get monitor process status."""
    # Fast process check
    try:
        # Use a faster check
        result = subprocess.run(
            ["pgrep", "-f", "start_monitor.py"],
            capture_output=True,
            timeout=1,  # Shorter timeout
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
        # Timeout may mean no process or slow check
        pass
    except:
        pass

    return {
        "running": False,
        "pid": None
    }


@app.post("/api/monitor/start")
async def start_monitor():
    """Start monitor process."""
    global monitor_process

    # Quick check whether already running (non-blocking)
    try:
        quick_check = subprocess.run(
            ["pgrep", "-f", "start_monitor.py"],
            capture_output=True,
            timeout=0.5  # Very short timeout
        )
        if quick_check.returncode == 0 and quick_check.stdout.strip():
            pid = int(quick_check.stdout.decode().strip().split('\n')[0])
            return {
                "status": "already_running",
                "message": f"Monitor process is already running (PID: {pid})",
                "pid": pid
            }
    except:
        pass  # Ignore check error and continue

    # Run startup in a background thread to avoid blocking API
    def start_in_background():
        try:
            # Stop old process
            subprocess.Popen(
                ["pkill", "-f", "start_monitor.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(0.5)  # Short wait

            # Clear log file
            if MONITOR_LOG_FILE.exists():
                MONITOR_LOG_FILE.write_text("")

            # Start new process
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
            print(f"Error starting monitor process: {e}")

    # Start in background thread and return immediately
    thread = threading.Thread(target=start_in_background, daemon=True)
    thread.start()

    # Return immediately
    return {
        "status": "started",
        "message": "Monitor start command executed. Please check status shortly."
    }


@app.post("/api/monitor/stop")
async def stop_monitor():
    """Stop monitor process."""
    global monitor_process

    with monitor_process_lock:
        if monitor_process is None or monitor_process.poll() is not None:
            return {
                "status": "not_running",
                "message": "Monitor process is not running"
            }

        try:
            # Try graceful shutdown
            monitor_process.terminate()
            monitor_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force stop
            monitor_process.kill()
            monitor_process.wait()
        except Exception as e:
            pass

        monitor_process = None

        # Also stop any leftover processes
        try:
            subprocess.run(["pkill", "-f", "start_monitor.py"],
                         capture_output=True, timeout=5)
        except:
            pass

        return {
            "status": "stopped",
            "message": "Monitor process stopped"
        }


# ============================================================
# Start server
# ============================================================


if __name__ == "__main__":
    # Listen on localhost only
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8888,
        reload=False,
        log_level="info"
    )
