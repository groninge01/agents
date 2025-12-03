#!/usr/bin/env python
"""启动止盈止损监控"""

import sys
sys.stdout.reconfigure(line_buffering=True)  # 实时输出

from scripts.python.position_monitor import PositionManager, show_config

if __name__ == "__main__":
    show_config()
    
    pm = PositionManager()
    pm.display_positions()
    
    if pm.positions:
        print('🔄 启动监控...')
        print('   每 30 秒检查一次')
        print('   按 Ctrl+C 停止')
        print()
        pm.monitor_loop()
    else:
        print('⚠️ 没有持仓，无需监控')

