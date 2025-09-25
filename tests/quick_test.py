#!/usr/bin/env python3
"""
快速测试Amazon抓取器
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


async def test_parser():
    """测试解析器功能"""
    print("🧪 测试Amazon解析器...")

    try:
        from app.parser import AmazonParser
        from playwright.async_api import async_playwright

        # 创建解析器
        parser = AmazonParser("amazon.com")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # 显示浏览器便于调试
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()

            # 测试一个真实的Amazon产品页面
            test_asin = "B08N5WRWNW"  # Echo Dot (4th Gen)
            url = f"https://amazon.com/dp/{test_asin}"

            print(f"📄 访问页面: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # 解析产品信息
            print("🔍 解析产品信息...")
            product = await parser.parse_product(page, test_asin)

            # 显示结果
            print(f"✅ 解析完成!")
            print(f"📦 标题: {product.title}")
            print(f"⭐ 评分: {product.rating}")
            print(f"💰 价格: ${product.price_amount} {product.price_currency}")
            print(
                f"🖼️  主图: {product.hero_image_url[:50]}..."
                if product.hero_image_url
                else "🖼️  主图: 未找到"
            )
            print(f"📝 要点数量: {len(product.bullets)}")
            print(f"🏷️  属性数量: {len(product.attributes)}")

            await browser.close()

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

    return True


async def test_database():
    """测试数据库连接"""
    print("\n🗄️  测试数据库连接...")

    try:
        from app.store import DatabaseService

        db = DatabaseService()

        # 测试连接
        result = (
            db.client.table("amazon_products").select("count", count="exact").execute()
        )
        print(f"✅ 数据库连接成功! 当前产品数量: {result.count}")

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("💡 请检查 .env 文件中的Supabase配置")
        return False

    return True


async def main():
    """主测试函数"""
    print("🚀 Amazon产品抓取器 - 快速测试")
    print("=" * 50)

    # 检查环境变量
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        print("💡 请复制 .env.example 为 .env 并填入正确的配置")
        return

    # 测试数据库
    db_ok = await test_database()
    if not db_ok:
        return

    # 测试解析器
    parser_ok = await test_parser()

    if parser_ok:
        print("\n🎉 所有测试通过!")
        print("🚀 可以启动服务器: python run.py")
    else:
        print("\n❌ 测试失败，请检查配置")


if __name__ == "__main__":
    asyncio.run(main())
