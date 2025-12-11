# 市场映射修复说明

## 🐛 问题描述

用户反馈："Seahawks vs. Falcons这条数据为什么和官方展示数据完全相反"

## 🔍 问题原因

代码中假设所有市场都遵循固定的映射：
- `outcomePrices[0]` = Yes 价格
- `outcomePrices[1]` = No 价格
- `clobTokenIds[0]` = Yes token
- `clobTokenIds[1]` = No token

但对于体育比赛等市场，这个假设是错误的：
- Outcomes 可能是 `["Seahawks", "Falcons"]` 而不是 `["Yes", "No"]`
- 如果市场问题是 "Will Seahawks win?"，那么：
  - Seahawks = Yes（应该对应问题中的队）
  - Falcons = No（对手）
- 如果市场问题是 "Will Falcons win?"，那么：
  - Falcons = Yes
  - Seahawks = No

**关键问题**：需要根据**问题文本**来判断哪个 outcome 对应 Yes，而不是简单地假设第一个是 Yes。

## ✅ 解决方案

创建了 `market_utils.py` 模块，实现了智能映射逻辑：

1. **标准 Yes/No 市场**：直接识别 "Yes"/"No" outcomes
2. **体育比赛市场**：根据问题模式识别：
   - "Will [Team] win?" → Team = Yes
   - "Will [Team] beat [Opponent]?" → Team = Yes
   - "[Team] vs [Opponent]" → 根据问题中的顺序判断

## 🔧 修改的文件

1. **新建**: `scripts/python/market_utils.py`
   - `parse_market_outcomes()`: 解析市场数据
   - `get_yes_no_mapping()`: 智能判断 Yes/No 映射
   - `get_price_for_side()`: 获取指定方向的价格
   - `get_token_id_for_side()`: 获取指定方向的 token ID
   - `get_market_info()`: 获取标准化的市场信息

2. **修改**: `scripts/python/batch_trade.py`
   - 使用新的工具函数来正确获取价格和 token IDs
   - 显示实际的方向名称（对于体育比赛显示队名）

## 📝 使用示例

### 修复前（错误）：
```python
# 假设第一个总是 Yes
yes_price = prices[0]
token_id = token_ids[0]
```

### 修复后（正确）：
```python
from scripts.python.market_utils import get_price_for_side, get_token_id_for_side

# 正确获取 Yes 价格和 token
yes_price = get_price_for_side(market, 'Yes')
yes_token = get_token_id_for_side(market, 'Yes')
```

## 🧪 测试

运行测试脚本验证映射是否正确：

```bash
python scripts/python/test_market_mapping.py
```

测试会：
1. 查找 Seahawks vs. Falcons 市场
2. 显示原始数据和映射结果
3. 验证价格总和是否合理（应该接近 1.0）

## ⚠️ 注意事项

1. **映射可能不完美**：如果问题格式特殊，可能无法正确识别，会使用默认映射并显示警告
2. **需要验证**：建议在实际使用前，对比官方数据验证映射是否正确
3. **扩展性**：可以根据需要添加更多的识别模式

## 🎯 下一步

1. 在实际市场数据上测试映射逻辑
2. 如果发现特定模式无法识别，添加更多识别规则
3. 考虑使用 AI 来解析问题并判断映射关系





