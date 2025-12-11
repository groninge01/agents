# 市场评分系统 (Market Scoring System)

## 📊 概述

市场评分系统根据 **5 个维度**给市场打分（总分 0-10 分），用于更科学、系统地评估市场的可交易性。

---

## 🎯 评分维度详解

### ① 流动性（0-3 分）

评估市场是否有足够的交易深度，避免大单滑点。

| 流动性范围 | 得分 |
|-----------|------|
| < $100k | 0 分 |
| $100k - $300k | 1 分 |
| $300k - $1M | 2 分 |
| ≥ $1M | 3 分 |

**代码位置**: `scripts/python/market_scorer.py` → `score_liquidity()`

---

### ② 活跃度（0-2 分）

评估市场最近 5 分钟的成交活跃程度。

| 活跃度 | 得分 | 判断标准 |
|-------|------|---------|
| 几十笔成交 | 2 分 | 最近5分钟成交量 > $10k |
| 偶尔成交 | 1 分 | 最近5分钟成交量 $1k - $10k |
| 不动 | 0 分 | 最近5分钟成交量 < $1k |

**判断方法**:
- 优先使用 24小时成交量估算：`volume_24hr / 288`（5分钟次数）
- 或使用总成交量作为粗略指标

**代码位置**: `scripts/python/market_scorer.py` → `score_activity()`

---

### ③ 波动空间（0-2 分）

评估历史/日内价格波动范围，波动越大交易机会越多。

| 波动范围（美分） | 得分 |
|----------------|------|
| ≥ 15c | 2 分 |
| 8c - 15c | 1 分 |
| < 8c | 0 分 |

**计算方法**:
- 使用 Yes/No 价格差异
- 或使用市场 spread 作为替代指标

**代码位置**: `scripts/python/market_scorer.py` → `score_volatility()`

---

### ④ 事件时间结构（0-2 分）

评估事件是否有明确的时间节点，便于预测和交易。

| 事件类型 | 得分 | 示例 |
|---------|------|------|
| 明确节点 | 2 分 | CPI、选举、FOMC、财报、发射 |
| 持续发酵 | 1 分 | 战争、危机、趋势 |
| 没节奏 | 0 分 | 其他 |

**判断关键词**:

**明确节点**:
- `cpi`, `consumer price index`, `inflation`
- `election`, `投票`, `选举`
- `fomc`, `fed meeting`, `interest rate`
- `earnings`, `财报`, `financial report`
- `jobs report`, `非农`
- `debate`, `辩论`
- `launch`, `发射`, `release`, `发布`

**持续发酵**:
- `war`, `战争`, `conflict`
- `crisis`, `危机`
- `trend`, `趋势`
- `ongoing`, `持续`

**补充规则**:
- 如果市场在 24 小时内结束，自动给 2 分（可能是明确节点）
- 如果市场在 48 小时内结束，给 1 分

**代码位置**: `scripts/python/market_scorer.py` → `score_event_structure()`

---

### ⑤ 情绪参与度（0-1 分）

评估社交媒体和新闻关注度，热度高的市场更容易出现价格波动。

| 参与度 | 得分 | 判断标准 |
|-------|------|---------|
| 社媒/新闻热 | 1 分 | 评论数 > 50，或包含热门关键词 |
| 冷清 | 0 分 | 其他 |

**热门关键词**:
- `trump`, `biden`, `president`
- `crypto`, `bitcoin`, `ethereum`
- `war`, `election`
- `trending`, `viral`
- `breaking`, `重大`

**代码位置**: `scripts/python/market_scorer.py` → `score_sentiment_engagement()`

---

## ✅ 总分解读

| 总分范围 | 解读 | 建议操作 |
|---------|------|---------|
| **≥ 7 分** | 可交易 ✅ | 可以正常交易 |
| **5-6 分** | 小仓 / 观察 ⚠️ | 可以小仓位交易或观察 |
| **< 5 分** | 跳过 ❌ | 不建议交易，跳过 |

---

## 💻 使用方法

### 方法 1: 直接调用评分函数

```python
from scripts.python.market_scorer import calculate_market_score, interpret_score

# 获取市场数据
market = {
    'question': 'Will Bitcoin reach $100k by end of year?',
    'liquidity': 500000,  # $500k
    'volume24hr': 50000,
    'outcomePrices': '[0.65, 0.35]',
    'endDate': '2024-12-31T23:59:59Z',
    # ... 其他字段
}

# 计算评分
score_data = calculate_market_score(market)

print(f"总分: {score_data['total_score']}/10")
print(f"解读: {interpret_score(score_data['total_score'])}")
print(f"可交易: {score_data['tradable']}")
```

### 方法 2: 在批量交易中使用（已集成）

```python
from scripts.python.batch_trade import find_short_term_markets
from agents.application.executor import Executor

executor = Executor()

# 查找评分 ≥ 7 分的市场
candidates = find_short_term_markets(
    gamma=gamma,
    hours=48,
    min_score=7,  # 只选择评分 ≥ 7 分的市场
    executor=executor
)
```

### 方法 3: 批量筛选市场

```python
from scripts.python.market_scorer import filter_markets_by_score

# 从所有市场中选择评分 ≥ 7 分的
tradable_markets = filter_markets_by_score(
    markets=all_markets,
    min_score=7,
    executor=executor
)
```

---

## 🔧 集成到现有代码

### 批量交易脚本已集成

`batch_trade.py` 已经集成了评分系统：

1. **自动评分**: 查找市场时自动计算评分
2. **按评分筛选**: 默认只选择评分 ≥ 7 分的市场
3. **显示评分详情**: 显示每个市场的详细评分
4. **按评分排序**: 优先选择评分高的市场

### 输出示例

```
📊 Step 1: 查找 48 小时内结束的市场（带评分系统）...
   找到 15 个符合条件的市场（评分 ≥ 7 分）

   市场评分详情:
   1. Will Bitcoin reach $100k by end of year?...
      总分: 8/10 - 可交易 ✅
      流动性: 3/3 | 活跃度: 2/2 | 波动: 1/2 | 事件结构: 1/2 | 情绪: 1/1
```

---

## 📝 配置选项

### 调整最低分数要求

在 `batch_trade.py` 中修改：

```python
# 只选择评分 ≥ 7 分的市场（可交易）
candidates = find_short_term_markets(gamma, hours=48, min_score=7)

# 选择评分 ≥ 5 分的市场（包括观察级别的）
candidates = find_short_term_markets(gamma, hours=48, min_score=5)

# 不筛选，显示所有市场（但仍然会计算评分）
candidates = find_short_term_markets(gamma, hours=48, min_score=None)
```

---

## 🎨 评分示例

### 示例 1: 高评分市场（8 分）

- **流动性**: $1.2M → 3 分
- **活跃度**: 最近5分钟几十笔成交 → 2 分
- **波动**: 18c 波动 → 2 分
- **事件结构**: CPI 报告（明确节点）→ 2 分
- **情绪**: 冷清 → 0 分
- **总分**: 9/10 → ✅ 可交易

### 示例 2: 中等评分市场（6 分）

- **流动性**: $250k → 1 分
- **活跃度**: 偶尔成交 → 1 分
- **波动**: 10c 波动 → 1 分
- **事件结构**: 持续发酵事件 → 1 分
- **情绪**: 热门话题 → 1 分
- **总分**: 6/10 → ⚠️ 小仓 / 观察

### 示例 3: 低评分市场（3 分）

- **流动性**: $50k → 0 分
- **活跃度**: 不动 → 0 分
- **波动**: 5c 波动 → 0 分
- **事件结构**: 没节奏 → 0 分
- **情绪**: 冷清 → 0 分
- **总分**: 3/10 → ❌ 跳过

---

## 🔍 评分逻辑优化建议

### 1. 活跃度评分优化

当前实现基于成交量估算，可以进一步优化：

- 接入实时交易数据 API
- 监控订单簿更新频率
- 分析最近 5 分钟的实际成交笔数

### 2. 波动空间评分优化

当前实现基于价格范围，可以进一步优化：

- 接入历史价格数据
- 计算日内真实波动率
- 分析价格趋势变化

### 3. 情绪参与度优化

当前实现基于关键词匹配，可以进一步优化：

- 接入社交媒体 API（Twitter, Reddit）
- 使用 AI 分析新闻热度
- 监控评论数量和讨论活跃度

### 4. 事件时间结构优化

可以进一步优化：

- 使用 AI 分析事件描述，识别明确节点
- 检查是否有预定的重要日期
- 分析历史类似事件的时间模式

---

## 📚 相关文件

- **评分模块**: `scripts/python/market_scorer.py`
- **批量交易**: `scripts/python/batch_trade.py`（已集成）
- **市场挑选逻辑文档**: `MARKET_SELECTION_LOGIC.md`

---

## 🎯 使用建议

1. **默认使用**: 建议默认使用评分 ≥ 7 分的市场（可交易级别）
2. **保守策略**: 可以提高到 ≥ 8 分，选择更高质量的市场
3. **激进策略**: 可以降低到 ≥ 5 分，包括观察级别的市场，但需要更谨慎
4. **组合使用**: 可以结合 AI 选择，先评分筛选，再 AI 选择最有把握的

---

## ✅ 总结

市场评分系统提供了一个**科学、系统、可量化**的方法来评估市场的可交易性，帮助你：

- ✅ 过滤低质量市场
- ✅ 优先选择高质量市场
- ✅ 量化市场评估标准
- ✅ 提高交易成功率

**立即开始使用**：运行 `batch_trade.py`，系统会自动使用评分系统筛选市场！






