#!/bin/bash
# 重启止盈止损监控脚本

# 获取项目根目录 (scripts/python -> scripts -> project_root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_ROOT"

echo "🔄 重启止盈止损监控..."
echo "   项目目录: $PROJECT_ROOT"
echo ""

# 停止旧进程
echo "⏹ 停止旧进程..."
pkill -f "start_monitor.py" 2>/dev/null
sleep 2

# 激活虚拟环境
source .venv/bin/activate
export PYTHONPATH="$PROJECT_ROOT"

# 确保 logs 目录存在
mkdir -p logs

# 清空旧日志
> logs/monitor.log

# 启动新监控
echo "🚀 启动监控..."
nohup python -u scripts/python/start_monitor.py > logs/monitor.log 2>&1 &
NEW_PID=$!

echo ""
echo "✅ 监控已启动！PID: $NEW_PID"
echo "   按 Ctrl+C 退出日志查看（监控会继续在后台运行）"
echo ""
echo "========================================"

# 自动输出日志
tail -f logs/monitor.log

