#!/usr/bin/env python3
"""
项目启动入口
"""
import subprocess
import sys
from pathlib import Path

def main():
    """主函数"""
    project_root = Path(__file__).parent
    script_path = project_root / "src" / "scripts" / "run.py"
    
    # 运行启动脚本
    subprocess.run([sys.executable, str(script_path)], cwd=project_root)

if __name__ == "__main__":
    main()