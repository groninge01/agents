# 市场挑选逻辑详解

## 📋 概述

系统使用**多阶段筛选 + AI 智能选择**的方式来挑选交易市场，确保选择最有价值和最可预测的市场。

---

## 🔍 主要市场挑选流程（batch_trade.py）

### Step 1: 查找短期市场 🎯

**函数**: `find_short_term_markets()`

#### 筛选条件：

1. **时间窗口** ⏰
   - 默认查找 **48 小时内结束**的市场
   - 原因：短期市场更容易预测，资金周转快

2. **流动性要求** 💰
   - 最低流动性：**$1,000** (可配置 `min_liquidity`)
   - 原因：确保有足够的交易深度，避免滑点过大

3. **价格合理性** 📊
   - Yes 价格必须在 **0.1 - 0.9** 之间
   - 原因：排除极端价格（接近 0 或 1），这些市场几乎没有交易价值

#### 代码逻辑：

```python
def find_short_term_markets(gamma, hours=48, min_liquidity=1000, count=30):
    markets = gamma.get_all_current_markets(limit=500)  # 获取最多500个活跃市场
    now = datetime.utcnow()
    deadline = now + timedelta(hours=hours)
    
    short_term = []
    for m in markets:
        # 检查结束时间
        if now < end_date <= deadline:
            # 检查流动性
            if liquidity > min_liquidity:
                # 检查价格合理性
                if 0.1 <= yes_price <= 0.9:
                    short_term.append(...)
    
    # 按流动性排序，返回前30个
    short_term.sort(key=lambda x: x['liquidity'], reverse=True)
    return short_term[:count]
```

#### 输出：
- 返回最多 **30 个**符合条件的市场
- 按**流动性从高到低**排序

---

### Step 2: AI 智能选择 🤖

**函数**: `ai_select_markets()`

#### 选择逻辑：

1. **AI 分析候选市场**
   - 将所有候选市场列表发送给 AI
   - AI 基于市场问题、剩余时间等信息进行判断
   - 优先选择 AI **最有把握预测**的市场

2. **提示词设计**：
   ```
   你是一个专业的体育/政治预测专家。以下是即将结束的预测市场：
   
   [市场列表，包含问题、价格、剩余时间]
   
   请选择 N 个你最有把握预测的市场。
   只返回市场编号，用逗号分隔。
   ```

3. **选择数量**
   - 根据用户设置的 `num_trades` 参数选择对应数量的市场
   - 如果 AI 选择不足，系统会自动补充

#### 代码逻辑：

```python
def ai_select_markets(executor, candidates, count=10):
    # 构建市场列表供 AI 分析
    market_list = []
    for i, m in enumerate(candidates, 1):
        market_list.append(
            f"{i}. {m['question']} "
            f"(Yes:{m['yes_price']:.0%}, {m['hours_left']:.0f}h后结束)"
        )
    
    # AI 选择
    prompt = f'''你是一个专业的体育/政治预测专家...
    {chr(10).join(market_list)}
    请选择 {count} 个你最有把握预测的市场。'''
    
    result = executor.llm.invoke([HumanMessage(content=prompt)])
    # 解析 AI 返回的市场编号
    selected_indices = re.findall(r'\d+', result.content)
    
    return selected_indices
```

---

### Step 3: 深度分析与交易决策 🔬

**函数**: `analyze_and_decide()`

#### 分析流程：

1. **AI 超级预测** 📈
   - 使用 `executor.get_superforecast()` 对每个市场进行深度分析
   - AI 会考虑：
     - 市场问题的背景信息
     - 历史数据
     - 当前市场情绪
     - 相关新闻和事件

2. **概率提取** 🎲
   - 从 AI 预测文本中提取概率值
   - 范围：0.05 - 0.95（避免极端值）

3. **交易方向决策** ⚖️
   - **买 Yes**: 如果 `AI概率 > 市场Yes价格 + 0.03`（有3%以上优势）
   - **买 No**: 如果 `AI概率 < 市场Yes价格 - 0.03`（市场高估了Yes）
   - **边缘值（Edge）**: `AI概率 - 市场价格`，用于评估交易价值

#### 代码逻辑：

```python
def analyze_and_decide(executor, market):
    # AI 超级预测
    prediction = executor.get_superforecast(
        event_title=question,
        market_question=question,
        outcome='Yes'
    )
    
    # 提取概率
    ai_prob = extract_probability_from_prediction(prediction)
    
    # 决定交易方向
    if ai_prob > yes_price + 0.03:  # 至少3%优势
        side = 'Yes'
        edge = ai_prob - yes_price
    elif ai_prob < yes_price - 0.03:
        side = 'No'
        edge = yes_price - ai_prob
    else:
        # 没有明显优势，根据概率决定
        side = 'Yes' if ai_prob >= 0.5 else 'No'
        edge = abs(ai_prob - yes_price)
    
    return {
        'side': side,      # 买入方向
        'ai_prob': ai_prob,  # AI 预测概率
        'edge': edge        # 市场边缘值
    }
```

---

## 📊 其他市场挑选策略

### 策略 2: 高流动性市场选择（auto_trade_and_monitor.py）

**特点**：
- 关注市场流动性（默认 > $5,000）
- 价格范围：0.15 - 0.85（更保守）
- 优先选择政治、科技、经济类（而非纯体育博彩）

**筛选条件**：
```python
if liquidity > MIN_LIQUIDITY and 0.15 <= yes_price <= 0.85:
    candidates.append(market)

# 按流动性排序，取前30个
candidates.sort(key=lambda x: x['liquidity'], reverse=True)
candidates = candidates[:30]

# AI 提示词
prompt = f'''优先选择：政治、科技、经济类（而非纯体育博彩）'''
```

---

### 策略 3: 按类别筛选（buy_by_category.py）

**特点**：
- 支持按市场类别（tags）筛选
- 例如：finance（金融）、culture（文化）、politics（政治）等
- 先筛选流动性，再通过 AI 分类

**流程**：
1. 预筛选：流动性 > $5,000，价格 0.1-0.9
2. AI 分类：将市场分类到指定类别
3. AI 选择：从每个类别中选择最佳市场

---

### 策略 4: Solana 市场（buy_solana_up_down.py）

**特点**：
- 专门针对 "Solana Up or Down" 市场
- 通过关键词和 slug 模式匹配
- 每 15 分钟开盘一次，需要轮询等待

**匹配方式**：
- 关键词：`"solana up or down"`, `"sol up/down"` 等
- Slug 模式：`sol-updown-15m`, `sol-updown` 等

---

## 🎯 核心挑选原则总结

### 1. **时间优先** ⏰
- 优先选择**短期市场**（48小时内结束）
- 原因：资金周转快，减少市场变化风险

### 2. **流动性优先** 💰
- 最低流动性要求：$1,000 - $5,000
- 按流动性排序，选择流动性最高的市场
- 原因：确保能顺利买卖，减少滑点

### 3. **价格合理** 📊
- Yes 价格范围：0.1 - 0.9（避免极端价格）
- 原因：极端价格的市场没有交易价值

### 4. **AI 智能筛选** 🤖
- 使用 AI 分析市场可预测性
- 优先选择 AI 最有把握的市场
- 原因：提高预测准确率

### 5. **边缘值判断** ⚖️
- 只有当 AI 预测与市场价格有**至少 3% 的差异**时才交易
- 计算边缘值（Edge）评估交易价值
- 原因：确保有足够的盈利空间

### 6. **主题偏好** 🎯
- 优先选择：政治、科技、经济类
- 避免：纯体育博彩类（不确定性高）
- 原因：这些领域更容易通过信息分析预测

---

## 📈 决策流程图

```
获取所有活跃市场 (最多500个)
         ↓
筛选 48 小时内结束的市场
         ↓
筛选流动性 > $1,000 的市场
         ↓
筛选价格在 0.1-0.9 的市场
         ↓
按流动性排序，取前 30 个
         ↓
AI 分析并选择最有把握的 N 个市场
         ↓
对每个选中的市场进行深度分析
         ↓
计算 AI 预测概率 vs 市场价格
         ↓
如果有 ≥3% 边缘值，生成交易计划
         ↓
执行交易
```

---

## ⚙️ 可配置参数

### batch_trade.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `hours` | 48 | 查找多少小时内结束的市场 |
| `min_liquidity` | 1000 | 最低流动性要求（美元） |
| `count` | 30 | 预筛选返回的市场数量 |
| `num_trades` | 10 | 最终选择的市场数量 |

### auto_trade_and_monitor.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MIN_LIQUIDITY` | 5000 | 最低流动性要求（美元） |
| `价格范围` | 0.15-0.85 | 更保守的价格范围 |
| `候选数量` | 30 | AI 选择前的候选数量 |

---

## 💡 优化建议

1. **调整时间窗口**：可以根据市场情况调整 `hours` 参数
2. **调整流动性要求**：根据资金量调整 `min_liquidity`
3. **调整边缘值阈值**：如果希望更保守，可以提高 3% 的阈值
4. **定制 AI 提示词**：可以修改 AI 提示词来适应不同的交易策略

---

## 📝 代码位置

- **主要逻辑**: `scripts/python/batch_trade.py`
- **辅助策略**: `scripts/python/auto_trade_and_monitor.py`
- **类别筛选**: `scripts/python/buy_by_category.py`
- **Solana 市场**: `scripts/python/buy_solana_up_down.py`






