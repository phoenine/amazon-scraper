#!/usr/bin/env python3
"""
测试Alembic迁移功能
"""
import os
import sys
import asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.database import get_database_url


def test_database_connection():
    """测试数据库连接"""
    print("🔗 测试数据库连接...")

    try:
        database_url = get_database_url()
        engine = create_engine(database_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1

        print("✅ 数据库连接成功")
        return True

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def test_alembic_config():
    """测试 Alembic 配置"""
    print("⚙️  测试 Alembic 配置...")

    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg_path = os.path.join(project_root, "database", "alembic.ini")

        if not os.path.exists(alembic_cfg_path):
            print(f"❌ Alembic 配置文件不存在: {alembic_cfg_path}")
            return False

        # 创建 Alembic 配置
        alembic_cfg = Config(alembic_cfg_path)

        # 设置数据库 URL
        database_url = get_database_url()
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

        print("✅ Alembic 配置正确")
        return True

    except Exception as e:
        print(f"❌ Alembic 配置失败: {e}")
        return False


def test_migration_creation():
    """测试迁移文件创建"""
    print("📝 测试迁移文件...")

    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        versions_dir = os.path.join(project_root, "database", "alembic", "versions")

        if not os.path.exists(versions_dir):
            print(f"❌ 迁移目录不存在: {versions_dir}")
            return False

        # 检查是否有迁移文件
        migration_files = [f for f in os.listdir(versions_dir) if f.endswith(".py")]

        if not migration_files:
            print("❌ 没有找到迁移文件")
            return False

        print(f"✅ 找到 {len(migration_files)} 个迁移文件")
        return True

    except Exception as e:
        print(f"❌ 迁移文件检查失败: {e}")
        return False


def test_migration_upgrade():
    """测试迁移升级"""
    print("⬆️  测试迁移升级...")

    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg_path = os.path.join(project_root, "database", "alembic.ini")

        alembic_cfg = Config(alembic_cfg_path)
        database_url = get_database_url()
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

        # 执行迁移
        command.upgrade(alembic_cfg, "head")

        print("✅ 迁移升级成功")
        return True

    except Exception as e:
        print(f"❌ 迁移升级失败: {e}")
        return False


def test_table_creation():
    """测试表创建"""
    print("🗃️  测试表创建...")

    try:
        database_url = get_database_url()
        engine = create_engine(database_url)

        # 检查表是否存在 - 删除已移除的表
        tables_to_check = [
            "amazon_products",
            "amazon_product_bullets",
            "amazon_product_images",
            # 删除 "amazon_product_attributes",
            "scrape_tasks",
        ]

        with engine.connect() as conn:
            for table in tables_to_check:
                result = conn.execute(
                    text(
                        f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )
                """
                    )
                )

                exists = result.fetchone()[0]
                if not exists:
                    print(f"❌ 表 {table} 不存在")
                    return False

                print(f"✅ 表 {table} 存在")

        print("✅ 所有必需的表都存在")
        return True

    except Exception as e:
        print(f"❌ 表检查失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("🧪 开始迁移测试...\n")

    tests = [
        test_database_connection,
        test_alembic_config,
        test_migration_creation,
        test_migration_upgrade,
        test_table_creation,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ 测试 {test.__name__} 出现异常: {e}\n")
            results.append(False)

    # 总结
    passed = sum(results)
    total = len(results)

    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败")

    return passed == total


if __name__ == "__main__":
    asyncio.run(main())
