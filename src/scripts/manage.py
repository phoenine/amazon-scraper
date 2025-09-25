#!/usr/bin/env python3
"""
数据库管理工具
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import argparse
from alembic.config import Config
from alembic import command


def get_alembic_config():
    """获取Alembic配置"""
    config_path = project_root / "config" / "alembic.ini"
    return Config(str(config_path))


def init_alembic():
    """初始化Alembic"""
    print("🔧 初始化Alembic...")

    # 创建alembic目录结构
    alembic_dir = project_root / "database" / "alembic" / "versions"
    os.makedirs(alembic_dir, exist_ok=True)

    # 使用正确的配置文件路径
    alembic_cfg = get_alembic_config()

    try:
        # 创建初始迁移
        command.revision(alembic_cfg, autogenerate=True, message="Initial migration")
        print("✅ Alembic初始化完成!")
        print("📝 已创建初始迁移文件")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")


def create_migration(message: str):
    """创建新的迁移文件"""
    print(f"📝 创建迁移: {message}")

    alembic_cfg = get_alembic_config()

    try:
        command.revision(alembic_cfg, autogenerate=True, message=message)
        print("✅ 迁移文件创建成功!")
    except Exception as e:
        print(f"❌ 创建迁移失败: {e}")


def upgrade_database(revision: str = "head"):
    """升级数据库"""
    print(f"⬆️  升级数据库到: {revision}")

    alembic_cfg = get_alembic_config()

    try:
        command.upgrade(alembic_cfg, revision)
        print("✅ 数据库升级成功!")
    except Exception as e:
        print(f"❌ 数据库升级失败: {e}")


def downgrade_database(revision: str):
    """降级数据库"""
    print(f"⬇️  降级数据库到: {revision}")

    alembic_cfg = get_alembic_config()

    try:
        command.downgrade(alembic_cfg, revision)
        print("✅ 数据库降级成功!")
    except Exception as e:
        print(f"❌ 数据库降级失败: {e}")


def show_history():
    """显示迁移历史"""
    print("📚 迁移历史:")

    alembic_cfg = get_alembic_config()

    try:
        command.history(alembic_cfg)
    except Exception as e:
        print(f"❌ 获取历史失败: {e}")


def show_current():
    """显示当前版本"""
    print("📍 当前数据库版本:")

    alembic_cfg = get_alembic_config()

    try:
        command.current(alembic_cfg)
    except Exception as e:
        print(f"❌ 获取当前版本失败: {e}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("🗄️  数据库管理工具")
        print("=" * 40)
        print("使用方法:")
        print("  python manage.py init                    # 初始化Alembic")
        print("  python manage.py migrate <message>       # 创建新迁移")
        print("  python manage.py upgrade [revision]      # 升级数据库")
        print("  python manage.py downgrade <revision>    # 降级数据库")
        print("  python manage.py history                 # 显示迁移历史")
        print("  python manage.py current                 # 显示当前版本")
        print()
        print("示例:")
        print("  python manage.py init")
        print("  python manage.py migrate 'Add user table'")
        print("  python manage.py upgrade")
        print("  python manage.py downgrade -1")
        return

    command_name = sys.argv[1]

    if command_name == "init":
        init_alembic()
    elif command_name == "migrate":
        if len(sys.argv) < 3:
            print("❌ 请提供迁移消息")
            return
        message = sys.argv[2]
        create_migration(message)
    elif command_name == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        upgrade_database(revision)
    elif command_name == "downgrade":
        if len(sys.argv) < 3:
            print("❌ 请提供目标版本")
            return
        revision = sys.argv[2]
        downgrade_database(revision)
    elif command_name == "history":
        show_history()
    elif command_name == "current":
        show_current()
    else:
        print(f"❌ 未知命令: {command_name}")


if __name__ == "__main__":
    main()
