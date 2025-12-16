# Solana Up or Down Market Buying Feature

## Feature status

### 1. **Market search** Completed

- **Location**: `scripts/python/buy_solana_up_down.py` → `find_solana_market()`
- **Search methods**:
  1. **Keyword search**: "solana up or down", "sol up/down", etc.
  2. **Slug pattern matching**: `sol-updown-15m`, `sol-updown`, `solana-updown`
- **Validation conditions**:
  - Market must be active (`active=True`)
  - Market must not be closed (`closed=False`)
  - Order book must be enabled (`enableOrderBook=True`)

### 2. **Market buying** Completed

- **Location**: `scripts/python/buy_solana_up_down.py` → `buy_solana_market()`
- **What it does**:
  - Automatically fetches the order book
  - Buys using the lowest ask price
  - Supports choosing Yes/No side
  - Supports dry run mode
  - Automatically adds the position to monitoring

### 3. **Polling buy** Completed

- **Location**: `scripts/python/buy_solana_up_down.py` → `poll_and_buy_solana()`
- **What it does**:
  - Polls every second to check whether the market is open
  - Buys immediately once an open market is found
  - Supports max wait time configuration (default 15 minutes)
  - Automatically adds to position monitoring (non-dry-run mode)

### 4. **API integration** Completed

- **Location**: `admin/api.py` → `execute_trade()`
- **Supported parameters**:
  - `market_type`: "auto" or "solana"
  - `solana_side`: "Yes" or "No"
  - `amount_per_trade`: Buy amount (max 1.0 USDC)
  - `dry_run`: Dry run

### 5. **Frontend UI** Partially completed

### 5. **Frontend UI** ⚠️ Partially completed

- **Status**: Backend API is supported, but the frontend UI does not yet expose a Solana market type option
- **Current behavior**:
  - Frontend only sends `market_type="auto"` (default)
  - UI options need to be added to choose "Solana Up or Down" market type

## 📋 Feature flow

### Market search flow

1. Fetch all active markets (up to 500)
2. For each market, check:
   - Question
   - Description
   - Slug (URL identifier)
3. Match keywords or slug patterns
4. Validate market status (active, not closed, order book enabled)

### Buy flow

1. Find the Solana market
2. Get token IDs
3. Select token ID based on side (Yes/No)
4. Fetch order book
5. Compute quantity using the lowest ask price
6. Execute buy order
7. Add to position monitoring (non-dry-run)

### Polling flow

1. Check markets once per second
2. If a market is found, check whether the order book is available
3. If the order book is available, execute buy
4. If buy succeeds, add to monitoring and return
5. If timeout occurs, return None

## 🔧 Usage

### Method 1: Run the script directly

```bash
# Dry run
python scripts/python/buy_solana_up_down.py

# Live trade
python scripts/python/buy_solana_up_down.py --execute
```

### Method 2: Call from Python

```python
from agents.polymarket.gamma import GammaMarketClient
from agents.polymarket.polymarket import Polymarket
from scripts.python.buy_solana_up_down import poll_and_buy_solana

gamma = GammaMarketClient()
polymarket = Polymarket()

result = poll_and_buy_solana(
    gamma=gamma,
    polymarket=polymarket,
    amount=1.0,           # Buy amount
    side='Yes',           # Or 'No'
    dry_run=False,        # Or True (dry run)
    max_wait_minutes=15   # Max wait time
)
```

### Method 3: Via API (requires frontend support)

```bash
curl -X POST http://localhost:8888/api/trade/execute \
  -H "Content-Type: application/json" \
  -d '{
    "num_trades": 1,
    "amount_per_trade": 1.0,
    "trade_type": "buy",
    "market_type": "solana",
    "solana_side": "Yes",
    "dry_run": false
  }'
```

## ⚠️ Notes

1. **Market open cadence**: Solana Up or Down markets open every 15 minutes
2. **Polling frequency**: checks once per second to catch the open quickly
3. **Max wait time**: default 15 minutes; adjustable in code
4. **Buy amount**: minimum $1.05 USDC (API limit)
5. **Position monitoring**: successful buys are automatically added to monitoring with take-profit/stop-loss support

## 🔍 Testing suggestions

1. **Test in dry-run mode first**:

   ```python
   poll_and_buy_solana(..., dry_run=True)
   ```

2. **Check logs**: verify the market is found
3. **Validate order book**: ensure the order book is available
4. **Test buying**: confirm the buy logic is correct

## 📝 TODO

- [ ] Add a Solana market type option in the frontend UI
- [ ] Add Solana market status display
- [ ] Improve error handling and retry logic
