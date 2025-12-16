# Market Mapping Fix

## 🐛 Problem

User report: "Why is the Seahawks vs. Falcons data the exact opposite of the official display?"

## 🔍 Root cause

The code assumed all markets follow a fixed mapping:

- `outcomePrices[0]` = Yes price
- `outcomePrices[1]` = No price
- `clobTokenIds[0]` = Yes token
- `clobTokenIds[1]` = No token

But for sports matchup markets this assumption is wrong:

- Outcomes may be `["Seahawks", "Falcons"]` instead of `["Yes", "No"]`
- If the market question is "Will Seahawks win?":
  - Seahawks = Yes (the team referenced in the question)
  - Falcons = No (the opponent)
- If the market question is "Will Falcons win?":
  - Falcons = Yes
  - Seahawks = No

**Key point**: you must infer which outcome corresponds to Yes from the **question text**, not assume the first outcome is Yes.

## ✅ Fix

Created the `market_utils.py` module to implement smarter mapping:

1. **Standard Yes/No markets**: directly detect "Yes"/"No" outcomes
2. **Sports matchup markets**: infer based on question patterns:
   - "Will [Team] win?" → Team = Yes
   - "Will [Team] beat [Opponent]?" → Team = Yes
   - "[Team] vs [Opponent]" → infer from question/ordering

## 🔧 Files changed

1. **Created**: `scripts/python/market_utils.py`

   - `parse_market_outcomes()`: parse market data
   - `get_yes_no_mapping()`: infer Yes/No mapping
   - `get_price_for_side()`: get price for a side
   - `get_token_id_for_side()`: get token ID for a side
   - `get_market_info()`: get normalized market info

2. **Updated**: `scripts/python/batch_trade.py`
   - Use the new utility functions to fetch correct prices and token IDs
   - Display the actual side label (for sports matchups, show team name)

## 📝 Example usage

### Before (wrong)

```python
# Assume the first outcome is always Yes
yes_price = prices[0]
token_id = token_ids[0]
```

### After (correct)

```python
from scripts.python.market_utils import get_price_for_side, get_token_id_for_side

# Correctly get the Yes price and token
yes_price = get_price_for_side(market, 'Yes')
yes_token = get_token_id_for_side(market, 'Yes')
```

## 🧪 Testing

Run the test script to verify mapping:

```bash
python scripts/python/test_market_mapping.py
```

The test will:

1. Find the Seahawks vs. Falcons market
2. Print raw data and mapping results
3. Verify that the price sum is reasonable (should be close to 1.0)

## ⚠️ Notes

1. **Mapping may not be perfect**: unusual question formats may not be recognized; fallback mapping will be used and a warning shown
2. **Verify**: compare with official data before relying on it
3. **Extensible**: you can add more detection patterns as needed

## 🎯 Next steps

1. Test mapping logic on real market data
2. Add more rules if you find patterns that are not recognized
3. Consider using AI to parse questions and infer mapping
