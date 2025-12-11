# Trading Execution Notes

## 如何执行真实交易

### 重要提示
1. **Dry Run 模式**: 如果勾选了 "Dry Run (Simulation Mode)" 复选框，系统只会模拟运行，**不会执行真实交易**。

2. **真实交易模式**: 要执行真实交易，必须**取消勾选** "Dry Run (Simulation Mode" 复选框。

### 执行步骤

1. **打开买入标签页**: 点击页面顶部的 "Buy" 标签

2. **填写交易参数**:
   - Number of Orders: 1-5 个市场
   - Amount per Order: 每个订单的金额（最大 1.0 USDC）

3. **确认执行模式**:
   - ✅ **真实交易**: **不要勾选** "Dry Run (Simulation Mode)" 复选框
   - 🔒 **模拟运行**: 勾选 "Dry Run (Simulation Mode)" 复选框

4. **点击 "Execute Buy" 按钮**

5. **查看确认对话框**:
   - 如果显示 "⚠️ ⚠️ ⚠️ LIVE TRADING MODE - Real money will be used! ⚠️ ⚠️ ⚠️" (红色背景)，表示将执行真实交易
   - 如果显示 "🔒 DRY RUN MODE - No real trades will be executed!" (黄色背景)，表示只是模拟运行

6. **确认执行**: 点击 "Confirm Execute" 按钮

7. **查看执行日志**:
   - 执行日志会在页面底部的 "Trading Logs" 面板中实时显示
   - 日志会显示每个交易步骤的详细信息

### 常见问题

**Q: 为什么点击购买后没有真实交易发生？**

A: 请检查以下几点：
1. 是否勾选了 "Dry Run (Simulation Mode)" 复选框？如果勾选了，只会模拟运行
2. 查看确认对话框中的执行模式显示
3. 查看 "Trading Logs" 面板中的日志，检查是否有错误信息
4. 检查钱包余额是否充足

**Q: 如何确认交易是否执行成功？**

A: 
1. 查看 "Trading Logs" 面板，日志会显示每个交易的执行结果
2. 查看 "Trading History" 中的任务状态
3. 如果交易成功，持仓会自动添加到监控列表中

**Q: 执行过程中出现错误怎么办？**

A:
1. 查看 "Trading Logs" 面板中的错误信息
2. 检查任务状态是否为 "Failed"
3. 常见错误：
   - 余额不足
   - 市场不存在或已关闭
   - 网络连接问题

### 技术说明

- 交易执行是异步的，会在后台线程中运行
- 日志会实时流式传输到前端
- 即使执行失败，也会在日志中显示详细的错误信息






