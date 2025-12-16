# Market Selection Logic (Detailed)

## 📋 Overview

The system selects trading markets using **multi-stage filtering + AI-assisted selection** to focus on the most valuable and most predictable markets.

---

## 🔍 Main market selection flow (`batch_trade.py`)

### Step 1: Find short-term markets 🎯

**Function**: `find_short_term_markets()`

#### Filters

1. **Time window** ⏰

   - By default, find markets that **end within 48 hours**
   - Rationale: short-term markets are easier to forecast and recycle capital faster

2. **Liquidity requirement** 💰

   - Minimum liquidity: **$1,000** (configurable via `min_liquidity`)
   - Rationale: ensure enough depth and avoid excessive slippage

3. **Price sanity check** 📊
   - Yes price must be between **0.1 - 0.9**
   - Rationale: exclude extreme prices (near 0 or 1) which usually offer little trading value

#### Code logic

```python
def find_short_term_markets(gamma, hours=48, min_liquidity=1000, count=30):
    markets = gamma.get_all_current_markets(limit=500)  # Fetch up to 500 active markets
    now = datetime.utcnow()
    deadline = now + timedelta(hours=hours)

    short_term = []
    for m in markets:
        # Check end time
        if now < end_date <= deadline:
            # Check liquidity
            if liquidity > min_liquidity:
                # Check price sanity
                if 0.1 <= yes_price <= 0.9:
                    short_term.append(...)

    # Sort by liquidity, return top 30
    short_term.sort(key=lambda x: x['liquidity'], reverse=True)
    return short_term[:count]
```

#### Output

- Returns up to **30** markets that meet the criteria
- Sorted by **liquidity (high to low)**

---

### Step 2: AI-assisted selection 🤖

**Function**: `ai_select_markets()`

#### Selection logic

1. **AI analyzes candidate markets**

   - Send the candidate list to the AI
   - The AI considers the market question, time remaining, etc.
   - Prefer markets the AI is **most confident** in forecasting

2. **Prompt design**

   ```
   You are a professional sports/politics forecasting expert. Below are prediction markets that are about to end:

   [Market list: question, price, time remaining]

   Select N markets you feel most confident forecasting.
   Return only the market numbers, separated by commas.
   ```

3. **Selection count**
   - Select the number of markets based on the user-configured `num_trades`
   - If the AI returns fewer than required, the system will auto-fill

#### Code logic

```python
def ai_select_markets(executor, candidates, count=10):
    # Build market list for AI analysis
    market_list = []
    for i, m in enumerate(candidates, 1):
        market_list.append(
            f"{i}. {m['question']} "
            f"(Yes:{m['yes_price']:.0%}, ends in {m['hours_left']:.0f}h)"
        )

    # AI selection
    prompt = f'''You are a professional sports/politics forecasting expert...
    {chr(10).join(market_list)}
    Select {count} markets you feel most confident forecasting.'''

    result = executor.llm.invoke([HumanMessage(content=prompt)])
    # Parse market indices returned by the AI
    selected_indices = re.findall(r'\d+', result.content)

    return selected_indices
```

---

### Step 3: Deep analysis and trade decision 🔬

**Function**: `analyze_and_decide()`

#### Analysis flow

1. **AI superforecast**

   - Use `executor.get_superforecast()` to deeply analyze each market
   - The AI considers:
     - background context
     - historical data
     - current market sentiment
     - relevant news and events

2. **Probability extraction**

   - Extract a probability from the AI's prediction text
   - Range: 0.05 - 0.95 (avoid extreme values)

3. **Trade direction decision**
   - **Buy Yes**: if `AI probability > market Yes price + 0.03` (≥ 3% edge)
   - **Buy No**: if `AI probability < market Yes price - 0.03` (market overprices Yes)
   - **Edge**: `AI probability - market price` (used to assess trade value)

#### Code logic

```python
def analyze_and_decide(executor, market):
    # AI superforecast
    prediction = executor.get_superforecast(
        event_title=question,
        market_question=question,
        outcome='Yes'
    )

    # Extract probability
    ai_prob = extract_probability_from_prediction(prediction)

    # Decide trade direction
    if ai_prob > yes_price + 0.03:  # At least 3% edge
        side = 'Yes'
        edge = ai_prob - yes_price
    elif ai_prob < yes_price - 0.03:
        side = 'No'
        edge = yes_price - ai_prob
    else:
        # No clear edge; decide based on probability
        side = 'Yes' if ai_prob >= 0.5 else 'No'
        edge = abs(ai_prob - yes_price)

    return {
        'side': side,        # Side to buy
        'ai_prob': ai_prob,  # AI probability
        'edge': edge         # Edge vs market
    }
```

---

## Other market selection strategies

### Strategy 2: High-liquidity market selection (`auto_trade_and_monitor.py`)

**Characteristics**:

- Focus on liquidity (default > $5,000)
- Price range: 0.15 - 0.85 (more conservative)
- Prefer politics/tech/economics (not pure sports betting)

**Filters**:

```python
if liquidity > MIN_LIQUIDITY and 0.15 <= yes_price <= 0.85:
    candidates.append(market)

# Sort by liquidity, take top 30
candidates.sort(key=lambda x: x['liquidity'], reverse=True)
candidates = candidates[:30]

# AI prompt
prompt = f'''Prefer: politics, technology, economics (not pure sports betting)'''
```

---

### Strategy 3: Filter by category (`buy_by_category.py`)

**Characteristics**:

- Support filtering by market category (tags)
- e.g. finance, culture, politics
- Filter by liquidity first, then classify via AI

**Flow**:

1. Pre-filter: liquidity > $5,000, price 0.1-0.9
2. AI classification: assign markets to target categories
3. AI selection: pick the best market from each category

---

### Strategy 4: Solana market (`buy_solana_up_down.py`)

**Characteristics**:

- Specialized for the "Solana Up or Down" market
- Match via keywords and slug patterns
- Opens every 15 minutes; requires polling

**Matching**:

- Keywords: `"solana up or down"`, `"sol up/down"`, etc.
- Slug patterns: `sol-updown-15m`, `sol-updown`, etc.

---

## Core principles summary

### 1. **Time first**

- Prefer **short-term markets** (end within 48 hours)
- Rationale: faster capital turnover and lower regime-change risk

### 2. **Liquidity first**

- Minimum liquidity: $1,000 - $5,000
- Sort by liquidity and pick the highest-liquidity markets
- Rationale: ensure smooth execution and reduce slippage

### 3. **Reasonable prices**

- Yes price range: 0.1 - 0.9 (avoid extremes)
- Rationale: extreme-price markets often offer little trading value

### 4. **AI filtering**

- Use AI to assess predictability
- Prefer markets where AI confidence is higher
- Rationale: improve forecast accuracy

### 5. **Edge threshold**

- Only trade when AI probability and market price differ by **at least 3%**
- Compute edge to assess trade value
- Rationale: ensure enough profit potential

### 6. **Topic preference**

- Prefer: politics, technology, economics
- Avoid: pure sports betting (high uncertainty)
- Rationale: these domains are often more forecastable using information analysis

---

## Decision flow

```
Fetch all active markets (up to 500)
         ↓
Filter markets ending within 48 hours
         ↓
Filter markets with liquidity > $1,000
         ↓
Filter markets with price in 0.1-0.9
         ↓
Sort by liquidity, take top 30
         ↓
AI analyzes and selects the top N highest-confidence markets
         ↓
Deep analysis for each selected market
         ↓
Compute AI probability vs market price
         ↓
If edge ≥ 3%, create a trade plan
         ↓
Execute trades
```

---

## Configurable parameters

### batch_trade.py

| Parameter       | Default | Description                                 |
| --------------- | ------- | ------------------------------------------- |
| `hours`         | 48      | End-within window in hours                  |
| `min_liquidity` | 1000    | Minimum liquidity (USD)                     |
| `count`         | 30      | Number of markets returned by pre-filtering |
| `num_trades`    | 10      | Final number of markets selected            |

### auto_trade_and_monitor.py

| Parameter         | Default   | Description                    |
| ----------------- | --------- | ------------------------------ |
| `MIN_LIQUIDITY`   | 5000      | Minimum liquidity (USD)        |
| `Price range`     | 0.15-0.85 | More conservative price range  |
| `Candidate count` | 30        | Candidates before AI selection |

---

## Suggestions

1. **Adjust the time window**: tune the `hours` parameter based on market conditions
2. **Adjust liquidity requirement**: tune `min_liquidity` based on your capital
3. **Adjust edge threshold**: raise the 3% threshold for a more conservative strategy
4. **Customize AI prompts**: adapt prompts to different trading styles

---

## 📝 Code locations

- **Main logic**: `scripts/python/batch_trade.py`
- **Auxiliary strategy**: `scripts/python/auto_trade_and_monitor.py`
- **Category filtering**: `scripts/python/buy_by_category.py`
- **Solana market**: `scripts/python/buy_solana_up_down.py`
