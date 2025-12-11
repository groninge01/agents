# 解决 422 错误

## 错误说明

422 Unprocessable Entity 错误表示请求数据格式不符合 API 的期望。

## 如何查看详细错误

1. **打开浏览器开发者工具** (F12 或右键 -> 检查)
2. **切换到 Console 标签页**
3. **点击购买按钮后，查看控制台输出**，你会看到：
   - `Sending trade request:` - 发送的请求数据
   - `Response status:` - 响应状态码
   - `API error response:` - 详细的错误信息

## 常见原因和解决方法

### 1. 字段类型不匹配
- **问题**: 字段类型错误（如字符串而不是数字）
- **解决**: 确保数据类型正确：
  - `num_trades`: 整数 (1-5)
  - `amount_per_trade`: 浮点数 (0.01-1.0)
  - `trade_type`: 字符串 ("buy" 或 "sell")
  - `dry_run`: 布尔值 (true/false)

### 2. 字段名称错误
- **问题**: 字段名称拼写错误
- **解决**: 确保使用正确的字段名：
  - `num_trades` (不是 `numTrades`)
  - `amount_per_trade` (不是 `amountPerTrade`)
  - `trade_type` (不是 `tradeType`)
  - `dry_run` (不是 `dryRun`)

### 3. 缺少必需字段
- **问题**: 缺少必需的字段
- **解决**: 确保所有字段都包含在请求中

### 4. 值超出范围
- **问题**: 值不符合验证规则
- **解决**: 
  - `num_trades`: 1-5
  - `amount_per_trade`: 0.01-1.0

## 测试 API

你可以使用 curl 测试 API：

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

## 检查清单

- [ ] 打开浏览器控制台查看详细错误
- [ ] 检查请求数据格式是否正确
- [ ] 检查字段名称是否拼写正确
- [ ] 检查数据类型是否正确
- [ ] 检查值是否在允许范围内
- [ ] 检查 API 服务是否正在运行

## 获取帮助

如果问题仍然存在，请提供：
1. 浏览器控制台的完整错误信息
2. 发送的请求数据 (从控制台 `Sending trade request:` 日志)
3. API 错误响应 (从控制台 `API error response:` 日志)






