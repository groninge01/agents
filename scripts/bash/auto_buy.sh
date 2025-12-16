#!/bin/bash
# Auto-buy script - accepts parameters

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR" && cd ../.. && pwd)"

cd "$PROJECT_ROOT"

# Default parameters
NUM_MARKETS=3
AMOUNT_PER_MARKET=1.0
DRY_RUN=false

# Help
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -n, --num <count>       Number of markets to buy (default: 3)"
    echo "  -a, --amount <amount>   Amount per market (default: 1.0)"
    echo "  -d, --dry-run           Dry run; do not execute real trades"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Buy 3 markets, \$1 each"
    echo "  $0 -n 5 -a 2.0          # Buy 5 markets, \$2 each"
    echo "  $0 -d                   # Dry run"
}

# Parse args
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
            echo "Unknown argument: $1"
            show_help
            exit 1
            ;;
    esac
done

# Print config
echo "========================================"
echo "🛒 Auto buy orders"
echo "========================================"
echo "  Markets: $NUM_MARKETS"
echo "  Amount per market: \$$AMOUNT_PER_MARKET"
echo "  Total: \$$(echo "$NUM_MARKETS * $AMOUNT_PER_MARKET" | bc)"
echo "  Mode: $([ "$DRY_RUN" = true ] && echo "🔒 Dry run" || echo "⚠️ Live trade")"
echo "========================================"
echo ""

# Activate virtual environment
source .venv/bin/activate
export PYTHONPATH="$PROJECT_ROOT"

# Execute purchases
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
    echo "✅ Done!"
    echo "========================================"

    if [ "$DRY_RUN" = false ]; then
        echo ""
        echo "💡 Start monitoring:"
        echo "   ./scripts/bash/restart_monitor_autosell.sh"
    fi
else
    echo ""
    echo "❌ Purchase failed! Exit code: $exit_code"
    exit $exit_code
fi
