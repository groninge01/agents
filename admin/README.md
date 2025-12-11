# Polymarket 交易管理后台使用说明

## 功能特性

1. ✅ **仅限 localhost 访问** - 确保安全，只能从本地访问
2. ✅ **用户名密码认证** - 使用环境变量配置，支持安全认证
3. ✅ **自动下单功能** - 可选择下单数和每单金额
4. ✅ **实时日志查看** - 支持实时滚动查看监控日志
5. ✅ **交易历史查看** - 查看所有交易任务的状态和日志

## 快速开始

### 1. 配置认证信息（可选）

默认用户名和密码：
- 用户名：`admin`
- 密码：`admin123`

**强烈建议修改默认密码！** 可以通过环境变量设置：

```bash
export ADMIN_USERNAME="your_username"
export ADMIN_PASSWORD="your_strong_password"
```

或者添加到 `.env` 文件：

```bash
ADMIN_USERNAME=your_username
ADMIN_PASSWORD=your_strong_password
```

### 2. 启动服务

```bash
# 方式1: 使用启动脚本（推荐，自动kill占用端口的进程）
bash admin/start.sh

# 方式2: 使用Python启动脚本
python admin/start.py

# 方式3: 直接运行API
python admin/api.py

# 方式4: 使用uvicorn
cd admin
uvicorn api:app --host 127.0.0.1 --port 8888
```

**推荐使用方式1**：`bash admin/start.sh` 会自动检查并kill占用端口8888的进程，确保服务正常启动。

### 3. 访问管理界面

打开浏览器访问：http://127.0.0.1:8888

首次访问会提示输入用户名和密码。

## 功能说明

### 自动下单

1. 填写下单数量（1-50）
2. 填写每单金额（USDC，0.01-1000）
3. 选择是否模拟运行（勾选后不会执行真实交易）
4. 点击"执行交易"按钮

系统会自动：
- 查找短期市场（48小时内结束）
- 使用AI选择最佳市场
- 分析市场并决定交易方向
- 执行批量交易

### 监控日志查看

1. 点击"开始监控"按钮开始实时查看监控日志
2. 日志会实时滚动显示
3. 点击"停止监控"停止查看
4. 点击"清空显示"清空当前显示的日志

### 交易日志查看

1. 在"交易历史"区域查看所有交易任务
2. 点击任务卡片查看该任务的详细日志
3. 日志会实时更新，直到任务完成

## 安全说明

1. **仅允许 localhost 访问** - 服务器只监听 127.0.0.1，无法从外部访问
2. **密码认证** - 使用 HTTP Basic 认证和 session token
3. **Token 有效期** - Session token 有效期为 24 小时
4. **密码安全** - 请使用强密码，避免使用默认密码

## 注意事项

1. 确保已正确配置 `.env` 文件，包含必要的 API 密钥
2. 确保钱包有足够的 USDC 余额
3. 首次使用建议先选择"模拟运行"测试功能
4. 监控日志来自 `logs/monitor.log` 文件
5. 交易日志保存在 `logs/batch_trade_*.log` 文件中

## API 接口

### 认证接口

- `POST /api/auth/login` - 登录获取 token

### 交易接口

- `POST /api/trade/execute` - 执行批量交易
- `GET /api/trade/list` - 获取交易任务列表
- `GET /api/trade/status/{task_id}` - 获取交易任务状态

### 日志接口

- `GET /api/logs/monitor` - 实时流式传输监控日志（SSE）
- `GET /api/logs/trade/{task_id}` - 实时流式传输交易日志（SSE）
- `GET /api/logs/monitor/history` - 获取监控日志历史

## 故障排查

### 无法访问管理界面

- 检查服务是否已启动
- 确认访问地址为 http://127.0.0.1:8888
- 检查防火墙设置

### 认证失败

- 确认用户名和密码正确
- 检查环境变量是否正确设置
- 清除浏览器缓存和 localStorage，重新登录

### 交易执行失败

- 检查钱包余额是否充足
- 查看交易日志了解详细错误信息
- 确认 API 密钥配置正确

## 技术栈

- **后端**: FastAPI
- **前端**: 原生 HTML/CSS/JavaScript
- **实时通信**: Server-Sent Events (SSE)
- **认证**: HTTP Basic Auth + Session Token

