# Cursor 控制台使用指南

## 📺 如何打开终端/控制台

### 方法 1: 快捷键（最快）⚡
- **Windows/Linux**: `Ctrl + ` `（反引号，Tab键上方）
- **Mac**: `Ctrl + ` ` 或 `Cmd + J`
- 可以快速切换显示/隐藏终端面板

### 方法 2: 通过菜单 📋
1. 点击顶部菜单栏
2. 选择 `Terminal` → `New Terminal`
3. 或选择 `View` → `Terminal`

### 方法 3: 命令面板 🎯
1. 按 `Ctrl + Shift + P`（Mac: `Cmd + Shift + P`）
2. 输入 "Terminal" 或 "终端"
3. 选择 `Terminal: Create New Terminal`

### 方法 4: 底部面板按钮 🔘
- 点击 Cursor 底部状态栏的 `Terminal` 图标
- 或者点击 `Problems`、`Output` 等标签旁边的小图标

## 🔍 查看不同类型的输出

### 1. Python 脚本输出
```bash
# 在终端中运行
python scripts/python/buy_solana_up_down.py

# 或使用 python3
python3 scripts/python/buy_solana_up_down.py
```

### 2. 日志文件输出
```bash
# 查看实时日志（如果脚本正在运行）
tail -f admin/logs/batch_trade_*.log

# 查看最新日志
ls -lt admin/logs/ | head -5
cat admin/logs/batch_trade_最新文件名.log
```

### 3. 服务输出（Admin 后台）
- Admin 后台运行在 `http://localhost:8888`
- 日志会输出到终端，你可以看到：
  - 启动信息
  - API 请求日志
  - 错误信息

### 4. 调试输出（Debug Console）
- 按 `F5` 启动调试
- 输出会显示在 "Debug Console" 面板

## 📊 终端面板布局

终端打开后，你会看到：

```
┌─────────────────────────────────────┐
│  Terminal                            │
│  ─────────────────────────────────  │
│  $ pwd                               │
│  /home/ericl/source_code/...        │
│                                      │
│  $ python script.py                  │
│  [脚本输出内容]                      │
│                                      │
│  ┌────────────────────────────────┐ │
│  │ >                               │ │ ← 命令输入区
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## 🎯 实用技巧

### 技巧 1: 分割终端
- 点击终端右上角的 `+` 按钮
- 或按 `Ctrl + Shift + ` ` 创建新终端
- 可以同时运行多个命令

### 技巧 2: 清除终端
- 输入 `clear` 命令
- 或按 `Ctrl + L`

### 技巧 3: 查找输出内容
- 在终端中按 `Ctrl + F`
- 可以搜索之前的输出内容

### 技巧 4: 滚动查看历史
- 使用鼠标滚轮
- 或使用终端滚动条

### 技巧 5: 复制终端内容
- 选中文本，自动复制
- 或右键选择 "Copy"

## 📝 查看项目日志

### Admin 后台日志
```bash
# 查看所有日志文件
ls -la admin/logs/

# 实时查看最新日志
tail -f admin/logs/batch_trade_*.log
```

### 监控日志
```bash
# 查看监控日志
cat scripts/python/monitor.log

# 实时查看（如果监控正在运行）
tail -f scripts/python/monitor.log
```

## 🔧 运行测试脚本

### 测试 Solana 市场查找
```bash
# 进入项目目录
cd /home/ericl/source_code/workspace_python/polymarket_agents

# 运行测试脚本（需要激活虚拟环境）
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate   # Windows

# 运行脚本
python scripts/python/buy_solana_up_down.py
```

### 启动 Admin 后台
```bash
cd admin
./start.sh

# 或者
python start.py
```

## ⚠️ 常见问题

### Q: 终端没有显示输出？
- 检查脚本是否真的在运行
- 检查脚本是否有 `print()` 语句
- 尝试添加 `flush=True` 到 print 语句

### Q: 如何查看之前的输出？
- 使用终端滚动条向上滚动
- 终端会保存所有历史输出

### Q: 输出太多，如何过滤？
```bash
# 使用 grep 过滤
python script.py | grep "错误"
python script.py | grep -i "success"
```

### Q: 如何保存输出到文件？
```bash
# 保存所有输出
python script.py > output.txt 2>&1

# 同时显示和保存
python script.py | tee output.txt
```

## 🎨 终端美化

### 使用彩色输出
```python
# 在 Python 脚本中使用颜色
print("\033[92m✅ 成功\033[0m")  # 绿色
print("\033[91m❌ 失败\033[0m")  # 红色
print("\033[93m⚠️  警告\033[0m")  # 黄色
```

## 📚 相关快捷键

- `Ctrl + ``: 切换终端显示/隐藏
- `Ctrl + Shift + ``: 创建新终端
- `Ctrl + L`: 清除终端
- `Ctrl + F`: 搜索终端内容
- `Ctrl + C`: 中断当前命令
- `Ctrl + D`: 关闭当前终端

## 💡 推荐设置

1. **自动保存终端历史**: 在设置中启用
2. **增加终端字体大小**: 设置 → Terminal → Font Size
3. **启用终端自动滚动**: 默认已启用

---

希望这个指南能帮助你更好地使用 Cursor 的终端功能！






