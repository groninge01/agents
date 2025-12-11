# 快速启动指南

## 🔧 修复 Python 模块导入问题

如果你遇到 `ModuleNotFoundError: No module named 'agents'` 错误，请按以下步骤操作：

### 方法 1: 从项目根目录运行（推荐）✅

```bash
# 确保在项目根目录
cd /home/ericl/source_code/workspace_python/polymarket_agents

# 激活虚拟环境（如果使用）
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 运行脚本
python scripts/python/buy_solana_up_down.py
```

### 方法 2: 设置 PYTHONPATH 环境变量

```bash
# Linux/Mac
export PYTHONPATH=/home/ericl/source_code/workspace_python/polymarket_agents:$PYTHONPATH
python scripts/python/buy_solana_up_down.py

# Windows (PowerShell)
$env:PYTHONPATH="C:\path\to\polymarket_agents;$env:PYTHONPATH"
python scripts/python/buy_solana_up_down.py
```

### 方法 3: 使用 -m 参数运行（推荐）✅

```bash
# 从项目根目录运行
cd /home/ericl/source_code/workspace_python/polymarket_agents
python -m scripts.python.buy_solana_up_down
```

## ✅ 已修复

我已经修复了 `buy_solana_up_down.py` 脚本，添加了自动路径设置代码。现在脚本应该可以正常工作了。

## 🧪 测试运行

运行以下命令测试：

```bash
# 从项目根目录
cd /home/ericl/source_code/workspace_python/polymarket_agents

# 激活虚拟环境（如果使用）
source .venv/bin/activate

# 运行脚本（模拟模式，不会真正购买）
python scripts/python/buy_solana_up_down.py
```

## 📝 注意事项

1. **确保在项目根目录运行**: 脚本需要找到 `agents` 和 `scripts` 目录
2. **激活虚拟环境**: 确保安装了所有依赖
3. **检查 .env 文件**: 确保配置了必要的环境变量

## 🔍 如果仍有问题

检查以下几点：

1. **虚拟环境是否激活**
   ```bash
   which python  # 应该显示虚拟环境路径
   ```

2. **依赖是否安装**
   ```bash
   pip list | grep -E "dotenv|httpx"  # 检查关键依赖
   ```

3. **项目结构是否正确**
   ```bash
   ls -la agents/  # 应该能看到 agents 目录
   ```






