#!/bin/bash
# 自动购买脚本 - 可传递参数

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR" && cd ../.. && pwd)"

cd "$PROJECT_ROOT"

# 默认参数
NUM_MARKETS=3
AMOUNT_PER_MARKET=1.0
DRY_RUN=false

# 帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -n, --num <数量>        购买市场数量 (默认: 3)"
    echo "  -a, --amount <金额>     每个市场金额 (默认: 1.0)"
    echo "  -d, --dry-run           模拟运行，不执行真实交易"
    echo "  -h, --help              显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                      # 购买 3 个市场，每个 \$1"
    echo "  $0 -n 5 -a 2.0          # 购买 5 个市场，每个 \$2"
    echo "  $0 -d                   # 模拟运行"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--num)
            NUM_MARKETS="$2"
            shift 2
            ;;
        -a|--amount)
            AMOUNT_PER_MARKET="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 显示配置
echo "========================================"
echo "🛒 自动购买订单"
echo "========================================"
echo "  市场数量: $NUM_MARKETS"
echo "  每笔金额: \$$AMOUNT_PER_MARKET"
echo "  总投资: \$$(echo "$NUM_MARKETS * $AMOUNT_PER_MARKET" | bc)"
echo "  模式: $([ "$DRY_RUN" = true ] && echo "🔒 模拟运行" || echo "⚠️ 真实交易")"
echo "========================================"
echo ""

# 激活虚拟环境
source .venv/bin/activate
export PYTHONPATH="$PROJECT_ROOT"

# 执行购买
if [ "$DRY_RUN" = true ]; then
    DRY_RUN_PY="True"
else
    DRY_RUN_PY="False"
fi

python -c "
from scripts.python.batch_trade import execute_batch_trades

execute_batch_trades(
    dry_run=${DRY_RUN_PY},
    amount_per_trade=${AMOUNT_PER_MARKET},
    num_trades=${NUM_MARKETS}
)
"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✅ 完成！"
    echo "========================================"
    
    if [ "$DRY_RUN" = false ]; then
        echo ""
        echo "💡 启动监控："
        echo "   ./scripts/bash/restart_monitor_autosell.sh"
    fi
else
    echo ""
    echo "❌ 购买失败！退出码: $exit_code"
    exit $exit_code
fi

