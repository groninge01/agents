"""
Position monitoring with take-profit / stop-loss
- Record purchased positions
- Periodically monitor price changes
- Auto-sell using take-profit / stop-loss rules
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

# Load .env configuration (override=True ensures existing env vars are overwritten)
load_dotenv(override=True)

# ============================================================
# 📋 Configuration parameters - read from .env
# ============================================================

# Take-profit / stop-loss settings (read from .env)
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.30"))    # Take-profit percentage: default 30%
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.15"))        # Stop-loss percentage: default 15%

# Monitoring settings (read from .env)
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "1"))       # Check interval (seconds): default 1s
AUTO_EXECUTE = os.getenv("AUTO_EXECUTE", "true").lower() == "true"  # Whether to auto-execute: default true

# File paths
POSITIONS_FILE = os.path.join(os.path.dirname(__file__), "positions.json")

# ============================================================


@dataclass
class Position:
    """Single position"""
    token_id: str           # Token ID
    market_question: str    # Market question
    side: str               # Yes or No
    buy_price: float        # Entry price
    quantity: float         # Position size (shares)
    cost: float             # Cost (USDC)
    buy_time: str           # Buy time
    take_profit: float      # Take-profit price (0 = disabled)
    stop_loss: float        # Stop-loss price (0 = disabled)
    status: str = "open"    # open, closed, expired
    order_id: str = ""      # Order ID

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class PositionManager:
    """Position manager"""

    def __init__(self):
        self.polymarket = Polymarket()
        self.gamma = GammaMarketClient()
        self.positions: list[Position] = []
        self.load_positions()

    def load_positions(self):
        """Load positions from file (force read latest data from disk)."""
        if os.path.exists(POSITIONS_FILE):
            try:
                # Retry reads to ensure we load the latest data
                import time
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        with open(POSITIONS_FILE, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.positions = [Position.from_dict(p) for p in data]
                        break  # Successfully read
                    except (json.JSONDecodeError, IOError) as e:
                        if attempt < max_retries - 1:
                            time.sleep(0.1)  # Wait for file write to finish
                            continue
                        else:
                            raise
            except Exception as e:
                print(f"⚠️ Failed to load positions file: {e}")
                self.positions = []
        else:
            self.positions = []

    def save_positions(self):
        """Save positions to file (atomic write to ensure data integrity)."""
        import time
        # Use atomic write to avoid concurrency issues
        temp_file = POSITIONS_FILE + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump([p.to_dict() for p in self.positions], f, indent=2, ensure_ascii=False)
                f.flush()  # Flush buffer
                os.fsync(f.fileno())  # Sync to disk

            # Atomic rename
            os.replace(temp_file, POSITIONS_FILE)
            # Ensure filesystem sync
            try:
                os.sync()  # Linux syscall to sync filesystem
            except:
                pass
        except Exception as e:
            # If it fails, fall back to direct write
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
                print(f"⚠️ Failed to save positions file: {e2}")

    def add_position(
        self,
        token_id: str,
        market_question: str,
        side: str,
        buy_price: float,
        quantity: float,
        cost: float,
        take_profit_pct: float = None,  # Take-profit percentage; None uses default
        stop_loss_pct: float = None,    # Stop-loss percentage; None uses default
        order_id: str = "",             # Order ID
    ):
        """Add a position (auto-deduplicate).

        Returns:
            tuple: (position, is_new) - the position object and whether it was newly added
        """
        # Reload to ensure we work from the latest positions list
        self.load_positions()

        # Check for an existing position (via order_id or token_id+status)
        if order_id:
            # Prefer checking by order_id
            existing = next((p for p in self.positions if p.order_id == order_id and p.order_id), None)
            if existing:
                print(f"⚠️  Order {order_id[:20]}... already exists, skipping add")
                return existing, False

        # Check if there is already an open position for this token_id
        existing_open = next((p for p in self.positions if p.token_id == token_id and p.status == "open"), None)
        if existing_open:
            # Merge positions: accumulate shares and cost; use a weighted average entry price
            print(f"📝 Existing open position found, merging size: {existing_open.market_question[:40]}...")
            print(f"   Previous: {existing_open.quantity:.6f} shares @ ${existing_open.buy_price:.4f}, cost ${existing_open.cost:.4f}")
            print(f"   New trade: {quantity:.6f} shares @ ${buy_price:.4f}, cost ${cost:.4f}")

            # Merge shares (sum)
            total_quantity = round(existing_open.quantity + quantity, 6)  # Keep 6 decimals

            # Accumulate total cost
            total_cost = round(existing_open.cost + cost, 6)  # Keep 6 decimals

            # Weighted average entry price: (old_qty*old_px + new_qty*new_px) / total_qty
            if total_quantity > 0:
                weighted_price = (
                    existing_open.quantity * existing_open.buy_price +
                    quantity * buy_price
                ) / total_quantity
                new_avg_buy_price = round(weighted_price, 6)  # Keep 6 decimals
            else:
                new_avg_buy_price = buy_price

            # Update position: accumulate shares/cost and update weighted average entry price
            existing_open.quantity = total_quantity
            existing_open.buy_price = new_avg_buy_price
            existing_open.cost = total_cost  # Accumulate cost across trades
            existing_open.buy_time = datetime.utcnow().isoformat()  # Update time to latest trade

            # Recompute take-profit / stop-loss based on new weighted average entry price
            if take_profit_pct is None:
                take_profit_pct = TAKE_PROFIT_PCT
            if stop_loss_pct is None:
                stop_loss_pct = STOP_LOSS_PCT

            if take_profit_pct > 0:
                existing_open.take_profit = round(min(new_avg_buy_price * (1 + take_profit_pct), 0.99), 6)
            if stop_loss_pct > 0:
                existing_open.stop_loss = round(max(new_avg_buy_price * (1 - stop_loss_pct), 0.01), 6)

            print(f"   ✅ After merge: {total_quantity:.6f} shares @ ${new_avg_buy_price:.4f} (weighted avg), total cost ${total_cost:.4f}")

            # Save updated positions
            self.save_positions()
            return existing_open, False  # False means it was not newly added (the existing position was updated)

        # Use default configuration
        if take_profit_pct is None:
            take_profit_pct = TAKE_PROFIT_PCT
        if stop_loss_pct is None:
            stop_loss_pct = STOP_LOSS_PCT
        # Compute take-profit / stop-loss prices
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
        """Get current sell price from APIs (bid price = best bid on the order book)."""

        # Method 1: Fetch bid price via order book API (most accurate and matches official sell price)
        try:
            orderbook = self.polymarket.get_orderbook(token_id)  # Wrapped method; auto-logs requests
            if orderbook and orderbook.bids:
                # bids may not be sorted; find the best bid
                best_bid = max(orderbook.bids, key=lambda x: float(x.price))
                return float(best_bid.price)
        except Exception as e:
            pass  # Fail silently and try other methods

        # Method 2: Fetch market prices via Gamma API
        # ⚠️ Important: map token_id to the corresponding outcome index (do not always use prices[0])
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

                    # Get token IDs list
                    token_ids_list = market.get('clobTokenIds', [])
                    if isinstance(token_ids_list, str):
                        token_ids_list = json.loads(token_ids_list)

                    # Get price list
                    prices = market.get('outcomePrices', [])
                    if isinstance(prices, str):
                        prices = json.loads(prices)

                    # Find the token_id index in the list
                    if token_ids_list and prices and len(token_ids_list) == len(prices):
                        try:
                            # Try to find the matching index
                            token_idx = token_ids_list.index(token_id)
                            if token_idx < len(prices):
                                return float(prices[token_idx])
                        except (ValueError, IndexError):
                            # If not found, fall back to the first price (with warning)
                            if len(prices) > 0:
                                print(f"⚠️ Warning: could not find token_id {token_id[:20]}... in outcomes index; using prices[0]")
                                return float(prices[0])
                    elif prices and len(prices) > 0:
                        # If token_ids list is unavailable, use the first price (legacy logic; may be inaccurate)
                        print(f"⚠️ Warning: could not retrieve token_ids list; using prices[0] (may be inaccurate)")
                        return float(prices[0])
        except Exception as e:
            pass

        return None

    def get_position_value_from_api(self, token_id: str, quantity: float) -> Optional[float]:
        """
        Get the current position value from APIs.

        Args:
            token_id: Token ID
            quantity: Position size

        Returns:
            Current value (USDC); returns None if unavailable
        """
        # Get current price from APIs
        current_price = self.get_current_price(token_id)

        if current_price is None:
            return None

        # Compute value using API price (matches official calculation)
        return round(current_price * quantity, 6)

    def check_position(self, position: Position) -> dict:
        """Check a single position status (using API data)."""
        result = {
            "token_id": position.token_id,
            "question": position.market_question,
            "side": position.side,
            "buy_price": position.buy_price,
            "quantity": position.quantity,
            "cost": position.cost,
            "take_profit": position.take_profit,
            "stop_loss": position.stop_loss,
            "current_price": position.buy_price,  # Default to entry price
            "pnl_pct": 0,
            "pnl_value": 0,
            "action": None,
            "reason": None,
            "order_id": getattr(position, 'order_id', '')  # Order ID
        }

        if position.status != "open":
            result["reason"] = "Closed"
            return result

        # Get current price (order book API)
        current_price = self.get_current_price(position.token_id)
        if current_price is None:
            result["reason"] = "Unable to fetch price"
            current_price = position.buy_price  # Fall back to entry price

        result["current_price"] = current_price

        # Get actual position size from blockchain API (real-time)
        actual_quantity = self.get_token_balance(position.token_id, wallet="both")
        if actual_quantity > 0:
            # Use actual amount returned by API
            result["quantity"] = round(actual_quantity, 6)
        else:
            # If there is no balance, use locally recorded quantity
            result["quantity"] = position.quantity

        # Compute PnL using API data (API price × API quantity)
        pnl_pct = (current_price - position.buy_price) / position.buy_price
        pnl_value = (current_price - position.buy_price) * result["quantity"]

        result["pnl_pct"] = pnl_pct
        result["pnl_value"] = pnl_value

        # Take-profit check (using configured take-profit percentage)
        if TAKE_PROFIT_PCT > 0 and pnl_pct >= TAKE_PROFIT_PCT:
            result["action"] = "SELL"
            result["reason"] = f"🟢 Take-profit triggered! Gain {pnl_pct*100:.1f}% >= {TAKE_PROFIT_PCT*100:.0f}%"

        # Stop-loss check (using configured stop-loss percentage)
        elif STOP_LOSS_PCT > 0 and pnl_pct <= -STOP_LOSS_PCT:
            result["action"] = "SELL"
            result["reason"] = f"🔴 Stop-loss triggered! Drawdown {abs(pnl_pct)*100:.1f}% >= {STOP_LOSS_PCT*100:.0f}%"

        # Backward-compatible TP/SL price checks (if set)
        elif position.take_profit > 0 and current_price >= position.take_profit:
            result["action"] = "SELL"
            result["reason"] = f"🟢 Take-profit triggered! Target price ${position.take_profit:.2f}"

        elif position.stop_loss > 0 and current_price <= position.stop_loss:
            result["action"] = "SELL"
            result["reason"] = f"🔴 Stop-loss triggered! Target price ${position.stop_loss:.2f}"

        return result

    def sync_positions_from_blockchain(self):
        """
        Sync actual position data from the blockchain.
        Compares local records with on-chain balances and updates differences.
        """
        print("🔄 Syncing positions from blockchain...")
        self.load_positions()

        # Get all wallet addresses
        api_addr = self.polymarket.client.get_address()
        proxy_addr = os.getenv("POLYMARKET_PROXY_WALLET")

        # Get token_ids for all open positions
        open_positions = [p for p in self.positions if p.status == "open"]
        token_ids = list(set([p.token_id for p in open_positions]))

        updated_count = 0
        new_positions = []

        # Check actual balance for each token
        for token_id in token_ids:
            try:
                # Get actual balance (API wallet + proxy wallet)
                api_balance = self.get_token_balance(token_id, wallet="api")
                proxy_balance = self.get_token_balance(token_id, wallet="proxy") if proxy_addr else 0.0
                actual_balance = api_balance + proxy_balance

                # Find all locally recorded open positions for this token
                local_positions = [p for p in open_positions if p.token_id == token_id]
                local_total_quantity = sum(p.quantity for p in local_positions)

                # Precision tolerance: allow 0.01 difference (precision issues)
                balance_diff = abs(actual_balance - local_total_quantity)

                if balance_diff > 0.01:  # Significant difference
                    print(f"  ⚠️  Token {token_id[:20]}... balance mismatch")
                    print(f"     Local record: {local_total_quantity:.6f}")
                    print(f"     Actual balance: {actual_balance:.6f}")
                    print(f"     Diff: {balance_diff:.6f}")

                    if actual_balance > local_total_quantity:
                        # Actual balance > local record: indicates a buy that wasn't recorded
                        # This should normally be recorded during trading, but we update for safety
                        if local_positions:
                            # Update the first position quantity (merge into the first)
                            pos = local_positions[0]
                            old_qty = pos.quantity
                            pos.quantity = round(actual_balance, 6)  # Use actual balance; keep 6 decimals
                            # If quantity increased, adjust cost proportionally (assumption)
                            if old_qty > 0:
                                pos.cost = round(pos.cost * (actual_balance / old_qty), 6)
                            print(f"     ✅ Updated position quantity: {old_qty:.6f} -> {actual_balance:.6f}")
                            updated_count += 1
                    elif actual_balance < local_total_quantity:
                        # Actual balance < local record: could be a partial sell
                        if local_positions:
                            # Update the first position quantity
                            pos = local_positions[0]
                            old_qty = pos.quantity
                            pos.quantity = round(actual_balance, 6)
                            # Adjust cost proportionally
                            if old_qty > 0 and actual_balance > 0:
                                pos.cost = round(pos.cost * (actual_balance / old_qty), 6)
                            else:
                                pos.cost = 0.0
                            print(f"     ✅ Updated position quantity: {old_qty:.6f} -> {actual_balance:.6f}")
                            updated_count += 1

                            # If balance is 0 (or close to 0), mark as closed
                            if actual_balance < 0.0001:
                                pos.status = "closed"
                                print(f"     📌 Position closed (balance is 0)")
            except Exception as e:
                print(f"  ⚠️  Sync token {token_id[:20]}... failed: {e}")
                continue

        if updated_count > 0:
            self.save_positions()
            print(f"✅ Synced {updated_count} positions")
        else:
            print("✅ All position data is consistent")
        print()

        return updated_count

    def check_all_positions(self) -> list[dict]:
        """Check all positions (reload before each check to ensure latest data)."""
        # Reload to ensure we use the latest position data
        self.load_positions()

        results = []
        for p in self.positions:
            if p.status == "open":
                results.append(self.check_position(p))
        return results

    def close_position(self, token_id: str, reason: str = "Manual close"):
        """Close a position (mark as closed)."""
        for p in self.positions:
            if p.token_id == token_id and p.status == "open":
                p.status = "closed"
                self.save_positions()
                return True
        return False

    def sync_stop_loss_take_profit(self):
        """Sync TP/SL prices for all positions (based on current config)."""
        updated_count = 0
        for p in self.positions:
            if p.status == "open":
                old_tp = p.take_profit
                old_sl = p.stop_loss

                # Recompute
                new_tp = min(p.buy_price * (1 + TAKE_PROFIT_PCT), 0.99) if TAKE_PROFIT_PCT > 0 else 0
                new_sl = max(p.buy_price * (1 - STOP_LOSS_PCT), 0.01) if STOP_LOSS_PCT > 0 else 0

                # Update
                if abs(new_tp - old_tp) > 0.001 or abs(new_sl - old_sl) > 0.001:
                    p.take_profit = round(new_tp, 4)
                    p.stop_loss = round(new_sl, 4)
                    updated_count += 1

        if updated_count > 0:
            self.save_positions()
            print(f"🔄 Synced TP/SL prices for {updated_count} positions")
            print(f"   TP: +{TAKE_PROFIT_PCT*100:.0f}% | SL: -{STOP_LOSS_PCT*100:.0f}%")
            print()

        return updated_count

    def get_token_balance(self, token_id: str, wallet: str = "api", max_retries: int = 3) -> float:
        """
        Get outcome token balance (with retries and rate-limit handling).

        Args:
            token_id: Token ID
            wallet: "api" = API private-key wallet, "proxy" = web proxy wallet, "both" = sum of both
            max_retries: Max retry attempts
        """
        balance_abi = '[{"inputs": [{"name": "account", "type": "address"}, {"name": "id", "type": "uint256"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]'

        def is_rate_limit_error(error) -> bool:
            """Check whether this is a rate-limit error."""
            error_str = str(error)
            error_lower = error_str.lower()

            # Check keywords in error message
            if 'rate limit' in error_lower or 'too many requests' in error_lower:
                return True
            if 'call rate limit exhausted' in error_lower:
                return True
            if 'retry in' in error_lower and ('10m' in error_lower or 'min' in error_lower):
                return True

            # Check dict-form errors
            if isinstance(error, dict):
                if error.get('code') == -32090:
                    return True
                if error.get('message', '').lower() in ['too many requests', 'rate limit']:
                    return True

            # Check exception args
            if hasattr(error, 'args') and error.args:
                for arg in error.args:
                    if isinstance(arg, dict) and arg.get('code') == -32090:
                        return True
                    arg_str = str(arg).lower()
                    if 'rate limit' in arg_str or 'too many requests' in arg_str:
                        return True

            return False

        def get_retry_delay(attempt: int) -> float:
            """Compute retry delay (exponential backoff)."""
            return min(2 ** attempt, 60)  # Max wait 60 seconds

        for attempt in range(max_retries):
            try:
                # Add delay between attempts to reduce rate-limit risk
                if attempt > 0:
                    delay = get_retry_delay(attempt)
                    print(f"⏳ Waiting {delay:.1f}s before retrying balance fetch (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(delay)

                ctf = self.polymarket.web3.eth.contract(address=self.polymarket.ctf_address, abi=balance_abi)

                api_balance = 0.0
                proxy_balance = 0.0

                # API wallet balance
                if wallet in ("api", "both"):
                    api_addr = self.polymarket.client.get_address()
                    api_balance = ctf.functions.balanceOf(api_addr, int(token_id)).call() / 1e6
                    # Small delay between requests
                    time.sleep(0.2)

                # Proxy wallet balance
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
                # Check whether this is a rate-limit error
                if is_rate_limit_error(e):
                    error_str = str(e)

                    # Try extracting retry timing info from the error message
                    retry_info = "10 minutes"
                    if 'retry in' in error_str.lower():
                        import re
                        match = re.search(r'retry in (\d+[mh]?\d*[ms]?)', error_str.lower())
                        if match:
                            retry_info = match.group(1)

                    # Try extracting more detailed information from the exception object
                    error_msg = error_str
                    if hasattr(e, 'args') and e.args:
                        # Check for dict-form error info in exception args
                        for arg in e.args:
                            if isinstance(arg, dict):
                                if 'message' in arg:
                                    error_msg = arg['message']
                                if 'data' in arg and isinstance(arg['data'], dict):
                                    if 'retry_in' in arg['data']:
                                        retry_info = arg['data']['retry_in']

                    if attempt < max_retries - 1:
                        print(f"⚠️ Rate limit hit: {error_msg}")
                        delay = get_retry_delay(attempt + 1)
                        print(f"   Retrying in {delay:.0f}s (attempt {attempt + 2}/{max_retries})...")
                        continue
                    else:
                        print(f"❌ Rate limit error (retried {max_retries} times): {error_msg}")
                        print(f"   💡 Suggestion: wait about {retry_info} and try again, or reduce request frequency")
                        print(f"   💡 You can:")
                        print(f"      1. Wait for a while and retry")
                        print(f"      2. Reduce monitoring frequency (increase interval)")
                        print(f"      3. Use local position data instead of real-time blockchain queries")
                        return 0.0
                else:
                    # Other errors: only print on the last attempt
                    if attempt == max_retries - 1:
                        print(f"⚠️ Unable to fetch token balance: {e}")
                        return 0.0
                    # Non rate-limit errors: wait and retry (may be transient)
                    delay = get_retry_delay(attempt + 1)
                    print(f"⏳ Error occurred, waiting {delay:.1f}s before retry (attempt {attempt + 2}/{max_retries})...")
                    time.sleep(delay)

        return 0.0

    def execute_sell(self, position: Position, reason: str, execute: bool = False) -> dict:
        """
        Execute a sell.

        Args:
            position: Position object
            reason: Sell reason
            execute: Whether to actually execute (False = simulated)
        """
        current_price = self.get_current_price(position.token_id)
        if current_price is None:
            return {"status": "error", "reason": "Unable to fetch current price"}

        # Check token balances
        api_balance = self.get_token_balance(position.token_id, wallet="api")
        proxy_balance = self.get_token_balance(position.token_id, wallet="proxy")

        # Use actual balance (tolerate small precision differences)
        sell_quantity = api_balance if api_balance > 0 else position.quantity

        print(f"⚠️ Preparing to sell: {position.market_question[:40]}...")
        print(f"   Reason: {reason}")
        print(f"   Recorded quantity: {position.quantity}")
        print(f"   Actual quantity: {sell_quantity:.4f}")
        print(f"   Entry price: ${position.buy_price:.2f}")
        print(f"   Current price: ${current_price:.2f}")

        pnl = (current_price - position.buy_price) * sell_quantity
        print(f"   Estimated PnL: ${pnl:+.2f}")

        if not execute:
            print("   📋 Simulated mode - no real trade executed")
            return {"status": "simulated", "reason": reason, "pnl": pnl}

        # Check if balance is sufficient
        if api_balance < 0.01:  # Too little balance
            print(f"   ❌ Insufficient token balance in API wallet!")
            print(f"      Recorded quantity: {position.quantity}")
            print(f"      API wallet balance: {api_balance}")
            print(f"      Proxy wallet balance: {proxy_balance}")

            if proxy_balance >= position.quantity * 0.99:  # Allow 1% error
                print(f"   💡 Token is in proxy wallet; please sell in the Polymarket web UI")
                return {"status": "error", "reason": f"Token is in proxy wallet; please sell in the web UI"}
            else:
                print(f"   💡 Please sell manually in the Polymarket web UI, or buy a new order via API")
                return {"status": "error", "reason": f"Insufficient balance in API wallet"}

        # Validate and adjust price: Polymarket CLOB API requires price in [0.001, 0.999]
        # This is an API limitation
        # ⚠️ Important: if price is 1.0, it must be adjusted to 0.999 (loses 0.001 in value)
        # Solution: prefer the actual best bid price from the order book if available; otherwise use 0.999
        sell_price = current_price

        # If price is close to 1.0, try to get a more accurate price from the order book
        if sell_price >= 0.99:
            print(f"   ⚠️ Price is close to 1.0 ({current_price:.4f}); checking order book for a more accurate price...")
            try:
                orderbook = self.polymarket.get_orderbook(position.token_id)
                if orderbook and orderbook.bids:
                    # Use the actual best bid price from the order book
                    best_bid = max(orderbook.bids, key=lambda x: float(x.price))
                    orderbook_price = float(best_bid.price)
                    if orderbook_price < 1.0 and orderbook_price >= 0.001:
                        sell_price = orderbook_price
                        print(f"   ✅ Using order book price: ${sell_price:.4f} (original: ${current_price:.4f})")
                    elif orderbook_price >= 1.0:
                        # Order book price is also 1.0; must use 0.999
                        sell_price = 0.999
                        loss = (1.0 - 0.999) * sell_quantity
                        print(f"   ⚠️ Order book price is also 1.0; adjusting to 0.999 (loss: ${loss:.4f})")
            except Exception as e:
                # If order book is missing or another error occurs, use 0.999 when price is 1.0
                print(f"   ⚠️ Unable to fetch order book price: {e}")
                if sell_price >= 1.0:
                    sell_price = 0.999
                    loss = (1.0 - 0.999) * sell_quantity
                    print(f"   ⚠️ Price 1.0 adjusted to 0.999 (API limitation; estimated loss: ${loss:.4f})")

        # Price range validation and adjustment (API requirement)
        if sell_price >= 1.0:
            # If still 1.0 (not handled above), adjust to 0.999
            sell_price = 0.999
            loss = (current_price - 0.999) * sell_quantity
            print(f"   ⚠️ Price adjusted to 0.999 (original {current_price:.4f})")
            print(f"   ⚠️ Estimated loss: ${loss:.4f} ({sell_quantity:.2f} shares × ${current_price - 0.999:.4f})")
        elif sell_price > 0.999:
            sell_price = 0.999  # API max price
            loss = (current_price - 0.999) * sell_quantity
            print(f"   ⚠️ Price adjusted to 0.999 (original {current_price:.4f})")
            print(f"   ⚠️ Estimated loss: ${loss:.4f} ({sell_quantity:.2f} shares × ${current_price - 0.999:.4f})")
        elif sell_price <= 0.0:
            sell_price = 0.001  # API min price
            print(f"   ⚠️ Price adjusted to 0.001 (original {current_price:.4f} below API minimum)")
        elif sell_price < 0.001:
            sell_price = 0.001
            print(f"   ⚠️ Price adjusted to 0.001 (original {current_price:.4f} below API minimum)")

        # Real sell (using adjusted price)
        try:
            result = self.polymarket.execute_order(
                price=sell_price,
                size=sell_quantity,
                side="SELL",
                token_id=position.token_id
            )

            # Mark position as closed
            position.status = "closed"
            self.save_positions()

            print(f"   ✅ Sell successful!")
            return {"status": "success", "reason": reason, "pnl": pnl, "result": result}

        except Exception as e:
            error_str = str(e)
            print(f"   ❌ Sell failed: {e}")

            # Check whether order book does not exist
            if "orderbook" in error_str.lower() and "does not exist" in error_str.lower():
                error_msg = "Order book does not exist, cannot sell via API. The market may be closed or settled. Please wait for settlement and handle it in the Polymarket web UI, or contact Polymarket support."
                print(f"   💡 Tip: {error_msg}")
                return {"status": "error", "reason": error_msg}
            elif "orderbook" in error_str.lower() and "404" in error_str:
                error_msg = "Order book does not exist (404). The market may be closed or settled; cannot sell via API. Please wait for settlement and handle it manually."
                print(f"   💡 Tip: {error_msg}")
                return {"status": "error", "reason": error_msg}
            else:
                return {"status": "error", "reason": str(e)}

    def display_positions(self):
        """Display all positions (reload first)."""
        # Reload to ensure we display the latest positions
        self.load_positions()

        print()
        print("=" * 80)
        print("📊 Current positions")
        print("=" * 80)

        open_positions = [p for p in self.positions if p.status == "open"]
        closed_positions = [p for p in self.positions if p.status == "closed"]
        total_positions = len(self.positions)

        print(f"Total positions: {total_positions} (open: {len(open_positions)}, closed: {len(closed_positions)})")

        if not open_positions:
            print("No open positions")
            if closed_positions:
                print(f"Closed positions: {len(closed_positions)}")
            return

        print()
        print(f"{'#':<3} {'Market':<35} {'Side':<5} {'Entry':<7} {'Now':<7} {'PnL':<8} {'TP':<7} {'SL':<7}")
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
        print(f"Total cost: ${total_cost:.2f} | Current value: ${total_value:.2f} | PnL: ${total_pnl:+.2f} ({total_pnl_pct:+.1f}%)")
        print()

    def monitor_loop(self, interval_seconds: int = None, auto_execute: bool = None):
        """
        Continuous monitoring loop.

        Args:
            interval_seconds: Check interval (seconds); None uses default
            auto_execute: Whether to auto-execute TP/SL; None uses default
        """
        # Use default configuration (from env vars)
        if interval_seconds is None:
            interval_seconds = MONITOR_INTERVAL
        if auto_execute is None:
            auto_execute = AUTO_EXECUTE

        print()
        print("=" * 70)
        print("🔄 Starting position monitor")
        print("=" * 70)
        print(f"   Interval: {interval_seconds} seconds")
        print(f"   Auto trade: {'✅ Enabled (REAL trades!)' if auto_execute else '❌ Disabled (alerts only)'}")
        print(f"   Take-profit threshold: +{TAKE_PROFIT_PCT*100:.0f}%")
        print(f"   Stop-loss threshold: -{STOP_LOSS_PCT*100:.0f}%")
        print("   Press Ctrl+C to stop")
        print("=" * 70)
        print()

        # Sync TP/SL prices for all positions (reload latest data first)
        self.load_positions()
        self.sync_stop_loss_take_profit()

        try:
            check_count = 0
            while True:
                check_count += 1

                # Sync actual on-chain positions (every 10 checks to avoid excessive frequency)
                if check_count == 1 or check_count % 10 == 0:
                    self.sync_positions_from_blockchain()

                # Reload before each check to ensure latest data (check_all_positions also reloads)
                results = self.check_all_positions()

                print()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check #{check_count}")

                # Table separator - shares first, compact Ask/Cost and Bid/Value, emphasize P&L
                sep = "+----------+------------------------------+------+------------+----------+----------+----------+"
                print(sep)
                print(f"| {'OrderID':<8} | {'Market':<28} | {'Side':<4} | {'Shares':>10} | {'Ask/Cost':>8} | {'Bid/Value':>8} | {'P&L':>9} |")
                print(sep)

                total_cost = 0
                total_value = 0

                for r in results:
                    question = r['question'][:25] + "..." if len(r['question']) > 28 else r['question']
                    pnl_pct = r['pnl_pct'] * 100

                    # Value = shares purchased × current market bid price
                    # r['current_price'] is best bid from the order book API (sell price)
                    # r['quantity'] is actual position size from blockchain API (shares)
                    current_value = r['current_price'] * r['quantity']

                    cost = r['cost']
                    order_id = r.get('order_id', '')[:8] if r.get('order_id') else '-'
                    shares = r['quantity']  # Shares

                    total_cost += cost
                    total_value += current_value

                    ask_price = r['buy_price']  # Ask price (used for buying)
                    bid_price = r['current_price']  # Bid price (current sell price)
                    shares_str = f"{shares:.6f}"  # Shares
                    # Ask/Cost combined: short display (no $) like "0.50/1.00"
                    ask_cost_str = f"{ask_price:.2f}/{cost:.2f}"
                    # Bid/Value combined: short display like "0.55/1.10"
                    bid_value_str = f"{bid_price:.2f}/{current_value:.2f}"
                    # P&L emphasized with extra width
                    pnl_str = f"{pnl_pct:+.1f}%"

                    print(f"| {order_id:<8} | {question:<28} | {r['side']:<4} | {shares_str:>10} | {ask_cost_str:>8} | {bid_value_str:>8} | {pnl_str:>9} |")

                    # Trigger TP/SL
                    if r.get("action") == "SELL":
                        print(f"|          >>> Trigger: {r['reason']:<67} |")

                        # Find the corresponding position and execute
                        for p in self.positions:
                            if p.token_id == r['token_id'] and p.status == "open":
                                self.execute_sell(p, r['reason'], execute=auto_execute)
                                break

                print(sep)
                total_pnl = total_value - total_cost
                total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
                # Total row: show total cost, total value, and total P&L
                print(f"| {'TOTAL':<8} | {'':<28} | {'':<4} | {'':<10} | {f'{total_cost:.2f}':>8} | {f'{total_value:.2f}':>8} | {f'{total_pnl_pct:+.1f}%':>9} |")
                print(sep)
                print(f"  Next check in {interval_seconds}s")

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print()
            print("=" * 70)
            print("⏹ Monitor stopped")
            print("=" * 70)

    def set_stop_loss_take_profit(self, token_id: str, take_profit_pct: float = 0, stop_loss_pct: float = 0):
        """
        Set TP/SL for an existing position.

        Args:
            token_id: Token ID
            take_profit_pct: Take-profit percentage (e.g. 0.2 = +20%)
            stop_loss_pct: Stop-loss percentage (e.g. 0.1 = -10%)
        """
        for p in self.positions:
            if p.token_id == token_id and p.status == "open":
                if take_profit_pct > 0:
                    p.take_profit = min(p.buy_price * (1 + take_profit_pct), 0.99)
                if stop_loss_pct > 0:
                    p.stop_loss = max(p.buy_price * (1 - stop_loss_pct), 0.01)
                self.save_positions()
                print(f"✅ Set: TP=${p.take_profit:.2f}, SL=${p.stop_loss:.2f}")
                return True
        print("❌ Position not found")
        return False


def show_config():
    """Show current configuration."""
    print()
    print("=" * 60)
    print("📋 Current configuration")
    print("=" * 60)
    print(f"  Take-profit %: {TAKE_PROFIT_PCT * 100:.0f}%")
    print(f"  Stop-loss %: {STOP_LOSS_PCT * 100:.0f}%")
    print(f"  Monitor interval: {MONITOR_INTERVAL} seconds")
    print(f"  Auto execute: {'✅ Enabled' if AUTO_EXECUTE else '❌ Disabled'}")
    print(f"  Positions file: {POSITIONS_FILE}")
    print("=" * 60)


def start_monitor():
    """Start monitor."""
    show_config()

    pm = PositionManager()
    pm.display_positions()

    if pm.positions:
        pm.monitor_loop()
    else:
        print("⚠️ No positions; monitoring not needed")


if __name__ == "__main__":
    show_config()

    pm = PositionManager()
    pm.display_positions()

    print()
    print("💡 Usage:")
    print("   1. Modify the configuration parameters at the top of this file")
    print("   2. After buying, call pm.add_position() to add a position")
    print("   3. Call pm.monitor_loop() to start monitoring")
    print()
