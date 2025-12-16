# Market Price Fetch Fix

## 🐛 Problem

User report: for the Seahawks vs. Falcons market, the displayed values were the exact opposite of the official website.

- **Official site**: bought Falcons at 25¢, now almost zero, PnL -$4.19 (-99.8%)
- **System**: No | $0.2500 | $0.9995 | ... | $+12.59 (+299.80%)

## 🔍 Root cause

### Issue 1: wrong price lookup

In `position_monitor.py` `get_current_price()`, when using the Gamma API as a fallback:

```python
# ❌ Wrong: always returns prices[0]
prices = data[0].get('outcomePrices', [])
if prices and len(prices) > 0:
    return float(prices[0])  # Problem: always uses the first price
```

**Problem**: if the user bought the Falcons token (possibly the second outcome), but the system always returned `prices[0]` (the first outcome price), then:

- The user actually holds Falcons (price near 0)
- The system shows Seahawks (price near 1.0)
- Result: completely inverted display

### Issue 2: mapping token ID to the correct price

We need to locate `token_id` in the `clobTokenIds` list to find its index, then return `outcomePrices[index]`.

## ✅ Fix

### Fix 1: get the correct price by token ID

Modify `get_current_price()` to find the index for the given token_id:

```python
# ✅ Correct: find the price index by token_id
token_ids_list = market.get('clobTokenIds', [])
prices = market.get('outcomePrices', [])

# Find token_id index in the list
token_idx = token_ids_list.index(token_id)
if token_idx < len(prices):
    return float(prices[token_idx])  # Return the matching price
```

### Fix 2: save the actual side label

When saving positions, store the real label (e.g. "Yes (Falcons)") rather than only "Yes" or "No":

```python
# Save as "Yes (Falcons)"
side_to_save = f"{t['side']} ({outcome_name})"
```

This helps:

1. Clearly show what was actually purchased
2. Make debugging/troubleshooting easier
3. Provide more intuitive display

## 🔧 Files changed

1. **`scripts/python/position_monitor.py`**

   - Fix `get_current_price()` to use token_id mapping

2. **`scripts/python/batch_trade.py`**
   - Save the actual side label (including outcome name) when persisting positions

## 📝 Verification

1. **Check saved positions**:

   - Open `scripts/python/positions.json`
   - The `side` field should look like "Yes (Falcons)" (or similar)

2. **Check price calculation**:

   - Run `python scripts/python/show_positions.py`
   - Prices should match the official website

3. **Compare to the website**:
   - Compare the same position on the website vs the system
   - Price and PnL should match

## ⚠️ Notes

1. **Old position data**: previously saved positions may still show the wrong side and may need manual update or re-adding

2. **Price source priority**:

   - Prefer order book API (more accurate)
   - Fallback Gamma API (mapping fixed)

3. **Token ID matching**: ensure `token_id` exists in `clobTokenIds`; otherwise a warning will be shown and fallback logic used

## 🎯 Next steps

1. Test the fix and verify prices are correct
2. If issues remain, search for other places using `prices[0]`
3. Consider adding more detailed logs for price fetching
