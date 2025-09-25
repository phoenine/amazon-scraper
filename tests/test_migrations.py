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

load_dotenv()


def test_database_connection():
    """测试数据库连接"""
    print("🔗 测试数据库连接...")

    try:
        from app.database import get_database_url

        database_url = get_database_url()
        engine = create_engine(database_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ 数据库连接成功!")
            print(f"📊 PostgreSQL版本: {version}")

        return True

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def test_alembic_config():
    """测试Alembic配置"""
    print("\n⚙️  测试Alembic配置...")

    try:
        alembic_cfg = Config("alembic.ini")

        # 检查配置文件
        script_location = alembic_cfg.get_main_option("script_location")
        print(f"📁 脚本位置: {script_location}")

        # 检查版本目录
        versions_dir = os.path.join(script_location, "versions")
        if os.path.exists(versions_dir):
            migrations = [f for f in os.listdir(versions_dir) if f.endswith(".py")]
            print(f"📝 现有迁移文件: {len(migrations)} 个")
        else:
            print("📝 版本目录不存在，需要初始化")

        return True

    except Exception as e:
        print(f"❌ Alembic配置测试失败: {e}")
        return False


def test_migration_creation():
    """测试迁移创建"""
    print("\n📝 测试迁移创建...")

    try:
        alembic_cfg = Config("alembic.ini")

        # 创建测试迁移
        print("创建测试迁移文件...")
        command.revision(alembic_cfg, autogenerate=True, message="Test migration")

        print("✅ 迁移文件创建成功!")
        return True

    except Exception as e:
        print(f"❌ 迁移创建失败: {e}")
        return False


def test_migration_upgrade():
    """测试迁移升级"""
    print("\n⬆️  测试迁移升级...")

    try:
        alembic_cfg = Config("alembic.ini")

        # 升级到最新版本
        print("升级数据库到最新版本...")
        command.upgrade(alembic_cfg, "head")

        print("✅ 数据库升级成功!")
        return True

    except Exception as e:
        print(f"❌ 数据库升级失败: {e}")
        return False


def test_table_creation():
    """测试表创建"""
    print("\n🗄️  测试表创建...")

    try:
        from app.database import get_database_url

        database_url = get_database_url()
        engine = create_engine(database_url)

        # 检查表是否存在
        tables_to_check = [
            "amazon_products",
            "amazon_product_bullets",
            "amazon_product_images",
            "amazon_product_attributes",
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
                status = "✅" if exists else "❌"
                print(f"{status} 表 {table}: {'存在' if exists else '不存在'}")

        return True

    except Exception as e:
        print(f"❌ 表检查失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🧪 Alembic迁移系统测试")
    print("=" * 50)

    # 检查环境变量
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        print("💡 请配置 .env 文件")
        return

    # 运行测试
    tests = [
        test_database_connection,
        test_alembic_config,
        # test_migration_creation,  # 注释掉，避免创建不必要的迁移
        # test_migration_upgrade,   # 注释掉，避免意外修改数据库
        # test_table_creation,      # 注释掉，需要先运行迁移
    ]

    results = []
    for test in tests:
        result = test()
        results.append(result)

    # 总结
    print("\n📊 测试结果:")
    print("=" * 30)
    passed = sum(results)
    total = len(results)
    print(f"✅ 通过: {passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过!")
        print("💡 下一步:")
        print("   1. python manage.py init     # 初始化迁移")
        print("   2. python manage.py upgrade  # 应用迁移")
    else:
        print("\n❌ 部分测试失败，请检查配置")


if __name__ == "__main__":
    asyncio.run(main())
