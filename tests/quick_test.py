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

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_parser():
    """测试解析器"""
    print("🔍 测试 Amazon 解析器...")

    try:
        from src.app.modules.parser import AmazonParser
        from playwright.async_api import async_playwright

        test_asin = "B08N5WRWNW"  # Echo Dot
        test_url = f"https://www.amazon.com/dp/{test_asin}"

        async with async_playwright() as p:
            print("🌐 启动浏览器...")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            print(f"📄 访问页面: {test_url}")
            await page.goto(test_url, wait_until="networkidle")

            parser = AmazonParser("amazon.com")

            print("🔍 解析产品信息...")
            product = await parser.parse_product(page, test_asin)

            # 显示结果
            print(f"✅ 解析完成!")
            print(f"📦 标题: {product.title}")
            print(f"⭐ 评分: {product.rating}")
            print(f"💰 价格: ${product.price_amount} {product.price_currency}")
            # 修改：从 hero_image_url 改为检查是否有 hero_image_url（ScrapedProduct模型中仍有此字段）
            print(
                f"🖼️  主图: {product.hero_image_url[:50]}..."
                if product.hero_image_url
                else "🖼️  主图: 未找到"
            )
            print(f"📝 要点数量: {len(product.bullets)}")
            # 删除属性数量显示
            # print(f"🏷️  属性数量: {len(product.attributes)}")

            await browser.close()

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

    return True


async def test_database():
    """测试数据库连接"""
    print("\n🗄️  测试数据库连接...")

    try:
        from src.app.modules.store import DatabaseService

        db = DatabaseService()

        # 测试获取不存在的产品
        product = await db.get_product("TEST123", "amazon.com")
        if product is None:
            print("✅ 数据库连接正常 (未找到测试产品)")
        else:
            print("⚠️  找到了测试产品")

    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        return False

    return True


async def main():
    """运行所有测试"""
    print("🧪 开始快速测试...\n")

    # 运行解析器测试
    parser_result = await test_parser()

    # 运行数据库测试
    db_result = await test_database()

    # 总结
    if parser_result and db_result:
        print("\n🎉 所有测试通过!")
        return True
    else:
        print("\n❌ 部分测试失败")
        return False


if __name__ == "__main__":
    asyncio.run(main())
