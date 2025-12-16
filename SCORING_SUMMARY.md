# Market Scoring System - Quick Reference

## 🎯 Scoring criteria (0-10 points)

### ① Liquidity (0-3 points)

- < $100k → 0 points
- $100k - $300k → 1 point
- $300k - $1M → 2 points
- ≥ $1M → 3 points

### ② Activity (0-2 points)

- Last 5 minutes: dozens of trades → 2 points
- Last 5 minutes: occasional trades → 1 point
- Last 5 minutes: no activity → 0 points

### ③ Volatility room (0-2 points)

- Historical/intraday: ≥ 15c → 2 points
- Historical/intraday: 8-15c → 1 point
- Historical/intraday: < 8c → 0 points

### ④ Event time structure (0-2 points)

- Clear milestone (CPI/election) → 2 points
- Ongoing buildup → 1 point
- No cadence → 0 points

### ⑤ Sentiment/engagement (0-1 point)

- Hot on social media/news → 1 point
- Quiet → 0 points

## ✅ Interpreting the total score

- **≥ 7**: Tradable ✅
- **5-6**: Small size / watch ⚠️
- **< 5**: Skip ❌

## 📁 File locations

- **Scoring module**: `scripts/python/market_scorer.py`
- **Integrated in**: `scripts/python/batch_trade.py`
- **Detailed doc**: `MARKET_SCORING_SYSTEM.md`

## 🚀 Usage

Already integrated: when you run the batch trading script, it will automatically use the scoring system to filter markets.
