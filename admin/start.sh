#!/bin/bash
# 启动管理后台服务（带错误检查）

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "🚀 启动 Polymarket 交易管理后台"
echo "========================================"
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "❌ 错误: 虚拟环境不存在"
    echo "   请先创建虚拟环境: python3 -m venv .venv"
    exit 1
fi

# 激活虚拟环境
source .venv/bin/activate

# 检查依赖
echo "📦 检查依赖..."
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "❌ 错误: uvicorn 未安装"
    echo "   请安装依赖: pip install -r requirements.txt"
    exit 1
fi

if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ 错误: fastapi 未安装"
    echo "   请安装依赖: pip install -r requirements.txt"
    exit 1
fi

# 设置环境变量
export PYTHONPATH="$PROJECT_ROOT"

# 检查并kill占用端口的进程
PORT=8888
echo "🔍 检查端口 $PORT 是否被占用..."

# 方法1: 使用lsof查找占用端口的进程
if command -v lsof >/dev/null 2>&1; then
    PIDS=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "⚠️  发现端口 $PORT 被以下进程占用: $PIDS"
        echo "   正在停止这些进程..."
        echo "$PIDS" | xargs kill -9 2>/dev/null
        sleep 1
    fi
fi

# 方法2: 使用fuser查找占用端口的进程（备选方案）
if command -v fuser >/dev/null 2>&1; then
    if fuser $PORT/tcp >/dev/null 2>&1; then
        echo "⚠️  使用fuser发现端口 $PORT 被占用"
        fuser -k $PORT/tcp 2>/dev/null
        sleep 1
    fi
fi

# 方法3: 查找并kill相关的admin进程
echo "🔍 查找并停止admin相关进程..."
pkill -f "admin/start.py" 2>/dev/null
pkill -f "admin.api" 2>/dev/null
pkill -f "uvicorn.*admin" 2>/dev/null

# 再次确认端口是否释放
sleep 1
if command -v lsof >/dev/null 2>&1; then
    if lsof -ti :$PORT >/dev/null 2>&1; then
        echo "❌ 警告: 端口 $PORT 仍然被占用，强制kill..."
        lsof -ti :$PORT | xargs kill -9 2>/dev/null
        sleep 1
    else
        echo "✅ 端口 $PORT 已释放"
    fi
fi

echo ""
echo "📍 访问地址: http://127.0.0.1:8888"
echo "🔒 仅允许 localhost 访问"
echo "⚠️  注意：当前已关闭用户认证"
echo "========================================"
echo ""

# 启动服务
python admin/start.py

