# Fixing 422 Errors

## What this error means

A 422 Unprocessable Entity error means the request body does not match what the API expects.

## How to view the detailed error

1. **Open browser dev tools** (F12 or right-click → Inspect)
2. **Switch to the Console tab**
3. **Click the buy button, then check console output**, you should see:
   - `Sending trade request:` - the request payload
   - `Response status:` - HTTP status code
   - `API error response:` - detailed error response

## Common causes and fixes

### 1. Field type mismatch

- **Problem**: wrong field types (e.g. string instead of number)
- **Fix**: ensure types are correct:
  - `num_trades`: integer (1-5)
  - `amount_per_trade`: float (0.01-1.0)
  - `trade_type`: string ("buy" or "sell")
  - `dry_run`: boolean (true/false)

### 2. Wrong field names

- **Problem**: typos in field names
- **Fix**: use the correct field names:
  - `num_trades` (not `numTrades`)
  - `amount_per_trade` (not `amountPerTrade`)
  - `trade_type` (not `tradeType`)
  - `dry_run` (not `dryRun`)

### 3. Missing required fields

- **Problem**: missing a required field
- **Fix**: ensure all required fields are included in the request

### 4. Value out of range

- **Problem**: value does not satisfy validation rules
- **Fix**:
  - `num_trades`: 1-5
  - `amount_per_trade`: 0.01-1.0

## Test the API

You can test the API with curl:

```bash
curl -X POST http://localhost:8888/api/trade/execute \
  -H "Content-Type: application/json" \
  -d '{
    "num_trades": 1,
    "amount_per_trade": 1.0,
    "trade_type": "buy",
    "dry_run": false
  }'
```

## Checklist

- [ ] Open the browser console and review the detailed error
- [ ] Check whether the request payload format is correct
- [ ] Check whether field names are spelled correctly
- [ ] Check whether data types are correct
- [ ] Check whether values are within allowed ranges
- [ ] Check whether the API service is running

## Getting help

If the issue persists, please provide:

1. The full error output from the browser console
2. The request payload (from `Sending trade request:`)
3. The API error response (from `API error response:`)
