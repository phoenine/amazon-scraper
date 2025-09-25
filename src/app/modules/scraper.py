import asyncio
from datetime import datetime, timedelta
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
        self.browser: Optional[Browser] = None
        self.semaphore = asyncio.Semaphore(settings.SCRAPER_GLOBAL_CONCURRENCY)

    async def init_browser(self):
        """Initialize browser instance"""
        if not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS
            )

    async def close_browser(self):
        """Close browser instance"""
        if self.browser:
            await self.browser.close()
            self.browser = None

    async def scrape_product(self, asin: str, marketplace: str) -> ScrapedProduct:
        """Scrape a single product"""
        async with self.semaphore:
            await self.init_browser()

            context = await self._create_context(marketplace)
            page = await context.new_page()

            try:
                # Navigate to product page
                url = f"https://{marketplace}/dp/{asin}"
                await page.goto(url, timeout=settings.BROWSER_TIMEOUT)

                # Check if blocked
                if await self._is_blocked(page):
                    raise Exception("Blocked by anti-bot measures")

                # Parse product data
                parser = AmazonParser(marketplace)
                product_data = await parser.parse_product(page, asin)

                return product_data

            finally:
                await page.close()
                await context.close()

    async def _create_context(self, marketplace: str) -> BrowserContext:
        """Create browser context with appropriate settings"""
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        # Set language based on marketplace
        locale_map = {
            "amazon.com": "en-US",
            "amazon.co.jp": "ja-JP",
            "amazon.de": "de-DE",
            "amazon.co.uk": "en-GB",
            "amazon.fr": "fr-FR",
        }

        locale = locale_map.get(marketplace, "en-US")
        await context.set_extra_http_headers(
            {
                "Accept-Language": f"{locale},en;q=0.9",
            }
        )

        return context

    async def _is_blocked(self, page) -> bool:
        """Check if page shows blocking/captcha"""
        # Check for common blocking indicators
        blocking_selectors = [
            '[data-testid="captcha"]',
            ".a-box-inner h4:has-text('Enter the characters you see below')",
            "form[action*='validateCaptcha']",
        ]

        for selector in blocking_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=1000)
                if element:
                    return True
            except:
                continue

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
            age = datetime.utcnow() - product.last_scraped_at
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
