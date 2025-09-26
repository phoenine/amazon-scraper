import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext

from ..config import settings
from .parser import AmazonParser
from .store import DatabaseService
from .models import ScrapedProduct


class ScraperService:
    """Amazon scraper service using Playwright"""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self._playwright = None
        self.max_retries = getattr(settings, "SCRAPER_MAX_RETRIES", 3)
        self.browser: Optional[Browser] = None
        self.semaphore = asyncio.Semaphore(settings.SCRAPER_GLOBAL_CONCURRENCY)

    async def init_browser(self):
        """Initialize browser instance"""
        if not self.browser:
            if not self._playwright:
                self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS
            )

    async def close_browser(self):
        """Close browser instance"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def scrape_product(self, asin: str, marketplace: str) -> ScrapedProduct:
        """Scrape a single product with simple retries and anti-bot hardening."""
        async with self.semaphore:
            await self.init_browser()

            last_err = None
            for attempt in range(1, self.max_retries + 1):
                context = await self._create_context(marketplace)
                page = await context.new_page()
                try:
                    # 轻微随机延迟，降低同质化
                    import random
                    await asyncio.sleep(random.uniform(0.8, 2.0))

                    url = f"https://{marketplace}/dp/{asin}"

                    await page.goto(
                        url,
                        timeout=settings.BROWSER_TIMEOUT,
                        wait_until="domcontentloaded",
                    )

                    await self._simulate_human_behavior(page)

                    if await self._is_blocked(page):
                        last_err = Exception("Blocked by anti-bot measures")
                        # 小退避 + 抖动
                        await asyncio.sleep(
                            min(4.0, 0.8 * attempt) + random.uniform(0, 0.6)
                        )
                        continue

                    parser = AmazonParser(marketplace)
                    product_data = await parser.parse_product(page, asin)
                    return product_data
                except Exception as e:
                    last_err = e
                    # 渐进退避
                    import random

                    await asyncio.sleep(
                        min(6.0, 1.5 * attempt) + random.uniform(0, 0.8)
                    )
                    continue
                finally:
                    await page.close()
                    await context.close()

            # 达到最大重试次数，抛出最后一次错误
            raise last_err if last_err else Exception("Unknown scrape error")

    async def _simulate_human_behavior(self, page):
        """Simulate human-like behavior"""
        import random

        # 随机滚动
        await page.evaluate(
            """
            window.scrollTo({
                top: Math.random() * 500,
                behavior: 'smooth'
            });
        """
        )

        # 随机等待
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # 模拟鼠标移动
        await page.mouse.move(random.randint(100, 800), random.randint(100, 600))

    async def _create_context(self, marketplace: str) -> BrowserContext:
        """Create browser context with enhanced anti-detection settings"""

        # 随机化用户代理
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        ]

        import random

        user_agent = random.choice(user_agents)

        # 轻微随机化视窗，减少指纹碰撞
        viewport = {
            "width": random.randint(1280, 1920),
            "height": random.randint(800, 1080),
        }

        context = await self.browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale=self._get_locale(marketplace),
            timezone_id=self._get_timezone(marketplace),
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": f"{self._get_locale(marketplace)},en;q=0.9",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
            java_script_enabled=True,
            bypass_csp=True,
        )

        # 注入反检测脚本
        await context.add_init_script(
            """
            // 移除webdriver属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // 伪造插件
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // 伪造语言
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            // 移除自动化痕迹
            window.chrome = {
                runtime: {},
            };

            // 伪造权限API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """
        )

        return context

    def _get_locale(self, marketplace: str) -> str:
        """Get locale for marketplace"""
        locale_map = {
            "amazon.com": "en-US",
            "amazon.co.jp": "ja-JP",
            "amazon.de": "de-DE",
            "amazon.co.uk": "en-GB",
            "amazon.fr": "fr-FR",
        }
        return locale_map.get(marketplace, "en-US")

    def _get_timezone(self, marketplace: str) -> str:
        """Get reasonable timezone for marketplace (reduces fingerprint mismatches)."""
        tz_map = {
            "amazon.com": "America/Los_Angeles",
            "amazon.co.jp": "Asia/Tokyo",
            "amazon.de": "Europe/Berlin",
            "amazon.co.uk": "Europe/London",
            "amazon.fr": "Europe/Paris",
        }
        return tz_map.get(marketplace, "America/Los_Angeles")

    async def _is_blocked(self, page) -> bool:
        """Check if page shows blocking/captcha"""
        blocking_selectors = [
            '[data-testid="captcha"]',
            ".a-box-inner h4:has-text('Enter the characters you see below')",
            "form[action*='validateCaptcha']",
        ]

        for selector in blocking_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=800)
                if element:
                    return True
            except:
                continue

        # 额外的文案/标题启发式
        try:
            title = await page.title()
            if any(
                x in (title or "")
                for x in ["Robot Check", "Bot Check", "CAPTCHA", "are not a robot"]
            ):
                return True
            content = await page.content()
            if any(
                kw in content
                for kw in [
                    "Enter the characters you see",
                    "To discuss automated access",
                    "automated requests",
                ]
            ):
                return True
        except:
            pass

        return False

    async def needs_scraping(
        self, asin: str, marketplace: str, force: bool = False
    ) -> bool:
        """Check if product needs scraping"""
        if force:
            return True

        product = await self.db_service.get_product(asin, marketplace)
        if not product:
            return True

        # Check if data is stale
        if product.last_scraped_at:
            if product.last_scraped_at.tzinfo is None:
                # 如果没有时区信息，假设是UTC
                last_scraped = product.last_scraped_at.replace(tzinfo=timezone.utc)
            else:
                last_scraped = product.last_scraped_at

            current_time = datetime.now(timezone.utc)
            age = current_time - last_scraped
            return age.total_seconds() > settings.SCRAPER_TTL_SECONDS

        return True

    async def wait_for_completion(
        self, asin: str, marketplace: str, timeout: int = 30
    ) -> Optional[dict]:
        """Wait for scraping to complete"""
        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            product = await self.db_service.get_product(asin, marketplace)
            if product and product.status == "fresh":
                return product
            await asyncio.sleep(1)

        return None
