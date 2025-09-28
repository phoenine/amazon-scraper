#!/usr/bin/env python3
"""
应用启动脚本
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import uvicorn

if __name__ == "__main__":
    # 设置环境变量
    os.environ.setdefault("PYTHONPATH", str(project_root))

    uvicorn.run(
        "src.app.main:app", host="0.0.0.0", port=18000, reload=True, log_level="debug"
    )
