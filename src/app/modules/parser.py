import re
import json
import logging
from typing import Optional, List, Dict, Any
from playwright.async_api import Page

from .models import ScrapedProduct

logger = logging.getLogger(__name__)


class AmazonParser:
    """Amazon product page parser"""

    def __init__(self, marketplace: str = "amazon.com"):
        self.marketplace = marketplace
        self.selectors = self._get_selectors_for_marketplace(marketplace)

    def _get_selectors_for_marketplace(self, marketplace: str) -> Dict[str, str]:
        """Get CSS selectors based on marketplace"""
        # Base selectors for amazon.com
        base_selectors = {
            "title": "#titleSection",
            "rating": "#acrPopover",
            "ratings_count": "#acrCustomerReviewText",
            "price": ".a-price .a-offscreen, .a-price",
            "price_symbol": ".a-price .a-price-symbol",
            "price_whole": ".a-price .a-price-whole",
            "price_fraction": ".a-price .a-price-fraction",
            "hero_image": "#imgTagWrapperId img",
            "gallery_images": "#altImages img",
            "bullets": "#feature-bullets ul li span",
        }

        if marketplace == "amazon.co.jp":
            base_selectors.update(
                {
                    "price": ".a-price .a-offscreen, #corePrice_desktop .a-offscreen",
                }
            )

        return base_selectors

    async def parse_product(self, page: Page, asin: str) -> ScrapedProduct:
        """Parse product page and extract all information"""
        logger.info(f"Parsing product {asin} from {self.marketplace}")

        try:

            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            #! 这里可以优化下
            await page.wait_for_timeout(2000)  # Additional wait for dynamic content

            # Extract all product information
            title = await self._extract_title(page)
            rating, ratings_count = await self._extract_rating_info(page)
            price_amount, price_currency = await self._extract_price(page)
            hero_image_url = await self._extract_hero_image(page)
            bullets = await self._extract_bullets(page)
            gallery_images = await self._extract_gallery_images(page)
            best_sellers_rank = await self._extract_bsr(page)

            # Get raw HTML for debugging (optional)
            raw_html = await page.content()

            return ScrapedProduct(
                asin=asin,
                marketplace=self.marketplace,
                title=title,
                rating=rating,
                ratings_count=ratings_count,
                price_amount=price_amount,
                price_currency=price_currency,
                hero_image_url=hero_image_url,
                bullets=bullets,
                gallery_images=gallery_images,
                best_sellers_rank=best_sellers_rank,
                raw_html=raw_html[:10000] if raw_html else None,  # Limit size
            )

        except Exception as e:
            logger.error(f"Error parsing product {asin}: {str(e)}")
            raise

    async def _safe_text(self, page: Page, selector: str) -> Optional[str]:
        """Safely extract text from element"""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                return " ".join(text.split()) if text else None
        except Exception as e:
            logger.debug(f"Error extracting text with selector '{selector}': {e}")
        return None

    async def _safe_attribute(
        self, page: Page, selector: str, attribute: str
    ) -> Optional[str]:
        """Safely extract attribute from element"""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.get_attribute(attribute)
        except Exception as e:
            logger.debug(
                f"Error extracting attribute '{attribute}' with selector '{selector}': {e}"
            )
        return None

    async def _extract_title(self, page: Page) -> Optional[str]:
        """Extract product title"""
        title = await self._safe_text(page, self.selectors["title"])
        return title.strip() if title else None

    async def _extract_rating_info(
        self, page: Page
    ) -> tuple[Optional[float], Optional[int]]:
        """Extract rating and ratings count"""
        rating = None
        ratings_count = None

        # Extract rating
        rating_text = await self._safe_text(page, self.selectors["rating"])
        if rating_text:
            # Try to extract rating from text like "4.6 out of 5 stars"
            rating_match = re.search(r"(\d+\.?\d*)\s*out\s*of\s*5", rating_text)
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                except ValueError:
                    pass

        # Extract ratings count
        ratings_text = await self._safe_text(page, self.selectors["ratings_count"])
        if ratings_text:
            count_match = re.search(r"([\d,]+)", ratings_text)
            if count_match:
                try:
                    ratings_count = int(count_match.group(1).replace(",", ""))
                except ValueError:
                    pass
        return rating, ratings_count

    async def _extract_price(self, page: Page) -> tuple[Optional[float], Optional[str]]:
        """Extract price amount and currency (simple, no prints)."""

        symbol_map = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY" if self.marketplace == "amazon.co.jp" else "CNY",
            "S$": "SGD",
        }

        price_text = await self._safe_text(page, self.selectors.get("price", ""))
        if price_text:
            m = re.search(r"([€$£¥]|S\$)?\s*([\d,]+\.?\d*)\s*([A-Z]{3})?", price_text)
            if m:
                sym, num, code = m.group(1), m.group(2), m.group(3)
                try:
                    amount = float(num.replace(",", ""))
                    currency = code or symbol_map.get(sym)
                    return amount, currency
                except ValueError:
                    pass

        try:
            currency_symbol = await self._safe_text(
                page, self.selectors.get("price_symbol", "")
            )
            price_whole = await self._safe_text(
                page, self.selectors.get("price_whole", "")
            )
            price_fraction = await self._safe_text(
                page, self.selectors.get("price_fraction", "")
            )

            if price_whole:
                num = price_whole.replace(",", "").strip()
                if price_fraction:
                    num = f"{num}.{price_fraction.strip()}"
                try:
                    amount = float(num)
                    currency = symbol_map.get(currency_symbol)
                    return amount, currency
                except ValueError:
                    pass
        except Exception as e:
            logger.debug(f"Error extracting price from components: {e}")

        return None, None

    async def _extract_hero_image(self, page: Page) -> Optional[str]:
        """Extract hero image URL"""
        # Try high-resolution image first
        hero_url = await self._safe_attribute(
            page, self.selectors["hero_image"], "data-old-hires"
        )
        if not hero_url:
            hero_url = await self._safe_attribute(
                page, self.selectors["hero_image"], "src"
            )

        # Clean up URL and get high-res version
        if hero_url:
            # Replace small image indicators with large ones
            hero_url = re.sub(r"_S[SX]\d+_", "_SL1500_", hero_url)
            hero_url = re.sub(r"\._.*?\.", ".", hero_url)

        return hero_url

    # 删除 _extract_availability 方法

    async def _extract_bullets(self, page: Page) -> List[str]:
        """Extract bullet points"""
        bullets = []
        try:
            bullet_elements = await page.query_selector_all(self.selectors["bullets"])
            for element in bullet_elements:
                text = await element.text_content()
                if text:
                    cleaned_text = " ".join(text.split()).strip()
                    if (
                        cleaned_text and len(cleaned_text) > 10
                    ):  # Filter out short/empty bullets
                        bullets.append(cleaned_text)
        except Exception as e:
            logger.debug(f"Error extracting bullets: {e}")

        return bullets[:5]  # Limit to 5 bullets as per requirement

    async def _extract_gallery_images(self, page: Page) -> List[Dict[str, Any]]:
        """Extract gallery images"""
        gallery = []
        try:
            image_elements = await page.query_selector_all(
                self.selectors["gallery_images"]
            )
            for idx, element in enumerate(image_elements):
                src = await element.get_attribute("src")
                if src:
                    # Convert to high-res version
                    high_res_src = re.sub(r"_S[SX]\d+_", "_SL1500_", src)
                    gallery.append(
                        {"url": high_res_src, "position": idx + 1, "role": "gallery"}
                    )
        except Exception as e:
            logger.debug(f"Error extracting gallery images: {e}")

        return gallery[:10]  # Limit gallery images

    async def _extract_bsr(self, page: Page) -> Optional[Dict[str, Any]]:
        """Extract Best Sellers Rank information"""
        bsr_data = {}
        try:
            # Look for BSR in product details
            bsr_text = await self._safe_text(
                page, "#SalesRank, #detailBulletsWrapper_feature_div"
            )
            if bsr_text and "Best Sellers Rank" in bsr_text:
                # Parse BSR text to extract rankings
                rank_matches = re.findall(r"#([\d,]+)\s+in\s+([^(]+)", bsr_text)
                for rank, category in rank_matches:
                    try:
                        rank_num = int(rank.replace(",", ""))
                        category_clean = category.strip()
                        bsr_data[category_clean] = rank_num
                    except ValueError:
                        continue
        except Exception as e:
            logger.debug(f"Error extracting BSR: {e}")

        return bsr_data if bsr_data else None
