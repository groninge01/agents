# Market Scoring System

## 📊 Overview

The market scoring system scores markets across **5 dimensions** (total score 0-10) to evaluate tradability in a more systematic way.

---

## 🎯 Scoring dimensions

### ① Liquidity (0-3)

Evaluate whether the market has sufficient depth to avoid large-order slippage.

| Liquidity range | Score |
| --------------- | ----- |
| < $100k         | 0     |
| $100k - $300k   | 1     |
| $300k - $1M     | 2     |
| ≥ $1M           | 3     |

**Code location**: `scripts/python/market_scorer.py` → `score_liquidity()`

---

### ② Activity (0-2)

Evaluate trading activity over the last 5 minutes.

| Activity          | Score | Rule                      |
| ----------------- | ----- | ------------------------- |
| Dozens of trades  | 2     | Last 5m volume > $10k     |
| Occasional trades | 1     | Last 5m volume $1k - $10k |
| No activity       | 0     | Last 5m volume < $1k      |

**How it is estimated**:

- Prefer using 24h volume estimate: `volume_24hr / 288` (number of 5-minute windows)
- Or fall back to total volume as a rough indicator

**Code location**: `scripts/python/market_scorer.py` → `score_activity()`

---

### ③ Volatility room (0-2)

Evaluate the historical/intraday price range; larger volatility usually means more opportunity.

| Volatility range (cents) | Score |
| ------------------------ | ----- |
| ≥ 15c                    | 2     |
| 8c - 15c                 | 1     |
| < 8c                     | 0     |

**How it is computed**:

- Use the Yes/No price difference
- Or use market spread as a proxy

**Code location**: `scripts/python/market_scorer.py` → `score_volatility()`

---

### ④ Event time structure (0-2)

Evaluate whether the event has a clear time milestone that makes forecasting/trading easier.

| Event type      | Score | Examples                                 |
| --------------- | ----- | ---------------------------------------- |
| Clear milestone | 2     | CPI, elections, FOMC, earnings, launches |
| Ongoing buildup | 1     | war, crisis, trends                      |
| No cadence      | 0     | other                                    |

**Keywords used for classification**:

**Clear milestone**:

- `cpi`, `consumer price index`, `inflation`
- `election`, `vote`
- `fomc`, `fed meeting`, `interest rate`
- `earnings`, `financial report`
- `jobs report`
- `debate`
- `launch`, `release`, `publish`

**Ongoing buildup**:

- `war`, `conflict`
- `crisis`
- `trend`
- `ongoing`

**Additional rules**:

- If the market ends within 24 hours, automatically score 2 (likely a clear milestone)
- If the market ends within 48 hours, score 1

**Code location**: `scripts/python/market_scorer.py` → `score_event_structure()`

---

### ⑤ Sentiment/engagement (0-1)

Evaluate social/news attention; hotter markets tend to move more.

| Engagement         | Score | Rule                                         |
| ------------------ | ----- | -------------------------------------------- |
| Hot on social/news | 1     | Comment count > 50, or contains hot keywords |
| Quiet              | 0     | other                                        |

**Hot keywords**:

- `trump`, `biden`, `president`
- `crypto`, `bitcoin`, `ethereum`
- `war`, `election`
- `trending`, `viral`
- `breaking`, `major`

**Code location**: `scripts/python/market_scorer.py` → `score_sentiment_engagement()`

---

## ✅ Interpreting the total score

| Total score | Interpretation        | Action                      |
| ----------- | --------------------- | --------------------------- |
| **≥ 7**     | Tradable ✅           | Trade normally              |
| **5-6**     | Small size / watch ⚠️ | Trade small size or observe |
| **< 5**     | Skip ❌               | Not recommended             |

---

## 💻 Usage

### Method 1: Call the scoring function directly

```python
from scripts.python.market_scorer import calculate_market_score, interpret_score

# Market data
market = {
    'question': 'Will Bitcoin reach $100k by end of year?',
    'liquidity': 500000,  # $500k
    'volume24hr': 50000,
    'outcomePrices': '[0.65, 0.35]',
    'endDate': '2024-12-31T23:59:59Z',
    # ... other fields
}

# Compute score
score_data = calculate_market_score(market)

print(f"Total score: {score_data['total_score']}/10")
print(f"Interpretation: {interpret_score(score_data['total_score'])}")
print(f"Tradable: {score_data['tradable']}")
```

### Method 2: Use in batch trading (already integrated)

```python
from scripts.python.batch_trade import find_short_term_markets
from agents.application.executor import Executor

executor = Executor()

# Find markets with score ≥ 7
candidates = find_short_term_markets(
    gamma=gamma,
    hours=48,
    min_score=7,  # Only select markets with score ≥ 7
    executor=executor
)
```

### Method 3: Filter markets in bulk

```python
from scripts.python.market_scorer import filter_markets_by_score

# Select markets with score ≥ 7 from all markets
tradable_markets = filter_markets_by_score(
    markets=all_markets,
    min_score=7,
    executor=executor
)
```

---

## 🔧 Integrate into existing code

### Batch trading script integration

`batch_trade.py` already integrates the scoring system:

1. **Automatic scoring**: compute the score while searching markets
2. **Filter by score**: by default only select markets with score ≥ 7
3. **Show score breakdown**: display detailed scores per market
4. **Sort by score**: prefer higher-scoring markets

### Output example

```
 Step 1: Find markets ending within 48 hours (with scoring)...
   Found 15 markets that meet criteria (score ≥ 7)

   Market score breakdown:
   1. Will Bitcoin reach $100k by end of year?...
      Total: 8/10 - Tradable
      Liquidity: 3/3 | Activity: 2/2 | Volatility: 1/2 | Event structure: 1/2 | Sentiment: 1/1
```

---

## Configuration options

### Adjust the minimum score threshold

Edit in `batch_trade.py`:

```python
# Only select markets with score ≥ 7 (tradable)
candidates = find_short_term_markets(gamma, hours=48, min_score=7)

# Select markets with score ≥ 5 (includes watch-level markets)
candidates = find_short_term_markets(gamma, hours=48, min_score=5)

# No filtering; show all markets (but still compute score)
candidates = find_short_term_markets(gamma, hours=48, min_score=None)
```

---

## 🎨 Scoring examples

### Example 1: High-scoring market (8)

- **Liquidity**: $1.2M → 3
- **Activity**: Dozens of trades in last 5 minutes → 2
- **Volatility**: 18c range → 2
- **Event structure**: CPI report (clear milestone) → 2
- **Sentiment**: Quiet → 0
- **Total**: 9/10 → ✅ Tradable

### Example 2: Medium-scoring market (6)

- **Liquidity**: $250k → 1
- **Activity**: Occasional trades → 1
- **Volatility**: 10c range → 1
- **Event structure**: Ongoing buildup event → 1
- **Sentiment**: Hot topic → 1
- **Total**: 6/10 → ⚠️ Small size / watch

### Example 3: Low-scoring market (3)

- **Liquidity**: $50k → 0
- **Activity**: No activity → 0
- **Volatility**: 5c range → 0
- **Event structure**: No cadence → 0
- **Sentiment**: Quiet → 0
- **Total**: 3/10 → ❌ Skip

---

## 🔍 Suggestions to improve scoring logic

### 1. Improve activity scoring

The current implementation estimates activity from volume; you can improve it by:

- Integrating real-time trade data APIs
- Monitoring order book update frequency
- Counting actual trades over the last 5 minutes

### 2. Improve volatility-room scoring

The current implementation uses price range; you can improve it by:

- Integrating historical price data
- Computing realized intraday volatility
- Analyzing trend changes

### 3. Improve sentiment/engagement scoring

The current implementation matches keywords; you can improve it by:

- Integrating social media APIs (Twitter, Reddit)
- Using AI to analyze news intensity
- Monitoring comment counts and discussion activity

### 4. Improve event time-structure scoring

You can further improve it by:

- Using AI to analyze event descriptions and identify clear milestones
- Checking for scheduled important dates
- Analyzing timing patterns of similar historical events

---

## 📚 Related files

- **Scoring module**: `scripts/python/market_scorer.py`
- **Batch trading**: `scripts/python/batch_trade.py` (integrated)
- **Market selection logic doc**: `MARKET_SELECTION_LOGIC.md`

---

## 🎯 Recommendations

1. **Default**: Use markets with score ≥ 7 (tradable level)
2. **Conservative**: Raise to ≥ 8 to pick higher-quality markets
3. **Aggressive**: Lower to ≥ 5 (includes watch-level markets), but be more cautious
4. **Combine**: Filter by score first, then use AI to pick the highest-conviction market

---

## ✅ Summary

The market scoring system provides a **systematic, quantitative** way to evaluate tradability and helps you:

- ✅ Filter out low-quality markets
- ✅ Prefer high-quality markets
- ✅ Quantify market evaluation criteria
- ✅ Improve trading success rate

**Start now**: run `batch_trade.py` and the system will automatically use scoring to filter markets.
