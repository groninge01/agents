#!/usr/bin/env python
"""
启动管理后台服务
"""

import os
import sys
import traceback

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 设置环境变量
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as e:
        print("❌ 错误: 无法导入 uvicorn")
        print(f"   请安装: pip install uvicorn")
        print(f"   详细错误: {e}")
        sys.exit(1)
    
    try:
        from admin.api import app
    except Exception as e:
        print("❌ 错误: 无法导入 admin.api")
        print(f"   详细错误: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    print("=" * 70)
    print("🚀 启动 Polymarket 交易管理后台")
    print("=" * 70)
    print(f"📍 访问地址: http://127.0.0.1:8888")
    print(f"🔒 仅允许 localhost 访问")
    print(f"⚠️  注意：当前已关闭用户认证")
    print("=" * 70)
    print()
    
    try:
        # 仅监听 localhost
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8888,
            log_level="info"
        )
    except Exception as e:
        print(f"❌ 服务启动失败: {e}")
        traceback.print_exc()
        sys.exit(1)

