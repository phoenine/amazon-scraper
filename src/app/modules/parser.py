import re
import json
import logging
from typing import Optional, List, Dict, Any
from playwright.async_api import Page

from .models import ScrapedProduct, AplusContent, AplusImage, AplusImageStatusEnum
from ..utils.image_extractor import AmazonImageExtractor

logger = logging.getLogger(__name__)


class AmazonParser:
    """Amazon产品页面解析器"""

    def __init__(self, page: Page, marketplace: str = "amazon.com"):
        self.page = page
        self.marketplace = marketplace
        self.selectors = self._get_selectors_for_marketplace(marketplace)
        self.image_extractor = AmazonImageExtractor(page, self.selectors)

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
            "hero_image": "#landingImage",
            "gallery_images": "#altImages li.item.imageThumbnail img",  # 缩略图
            "bullets": "#feature-bullets ul li span",
            # Product Details selectors
            "product_details_container": "#prodDetails, #productDetails",
            "product_details_table": "#productDetails_detailBullets_sections1, #productDetails_techSpec_section_1, .prodDetTable",
            "product_details_rows": "tr",
            "product_details_key": "th, .prodDetSectionEntry",
            "product_details_value": "td, .prodDetAttrValue",
            # A+ Content selectors
            "aplus_container": "#aplus, .aplus-v2, [data-aplus-module]",
            "aplus_brand_story_container": ".apm-brand-story-hero, .apm-brand-story-card, .brand-story-hero, .brand-story-card",
            "aplus_brand_story_text": ".apm-brand-story-text-bottom, .apm-brand-story-text, .apm-brand-story-slogan-text, .brand-story-text",
            "aplus_brand_story_images": ".apm-brand-story-background-image img, .apm-brand-story-image-img, .apm-brand-story-logo-image img, .brand-story-image img",
            "aplus_modules": ".aplus-v2 .aplus-module, .aplus-module, [data-aplus-module]",
            "aplus_faq_container": ".apm-brand-story-faq, .aplus-faq, .faq-section, .qa-section",
            "aplus_faq_question": "h3, h4, .question, .faq-question, .qa-question, dt",
            "aplus_faq_answer": "p, .answer, .faq-answer, .qa-answer, dd",
            "aplus_table_container": ".apm-tablemodule, .comparison-table, .product-details-table, .aplus-table",
            "aplus_table_rows": "tr",
            "aplus_table_cells": "td, th",
            "aplus_text_content": ".apm-tablemodule-valuecell, .apm-tablemodule-keyhead, .aplus-module p, .aplus-module h1, .aplus-module h2, .aplus-module h3, .aplus-module h4, .aplus-module h5, .aplus-module h6, .aplus-text",
            "aplus_images": ".aplus-module img, .apm-tablemodule img, .aplus-v2 img, [data-aplus-module] img",
            "aplus_from_brand_section": "h2:contains('From the brand'), h3:contains('From the brand')",
        }

        if marketplace == "amazon.co.jp":
            base_selectors.update(
                {
                    "price": ".a-price .a-offscreen, #corePrice_desktop .a-offscreen",
                }
            )

        return base_selectors

    async def parse_product(self, page: Page, asin: str) -> ScrapedProduct:
        """Parse Amazon product page and extract all relevant information"""
        try:
            logger.info(f"开始解析产品: {asin}")

            self.image_extractor.page = page

            #! 这里可以优化下
            await page.wait_for_timeout(2000)

            # Extract all product information
            title = await self._extract_title(page)
            rating, ratings_count = await self._extract_rating_info(page)
            price_amount, price_currency = await self._extract_price(page)
            hero_image_url = await self._extract_hero_image()
            bullets = await self._extract_bullets(page)
            gallery_images = await self._extract_gallery_images()
            best_sellers_rank = await self._extract_bsr(page)

            # Extract A+ content
            aplus_content, aplus_images = await self._extract_aplus_content(page)

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
                gallery_images=gallery_images,
                bullets=bullets,
                best_sellers_rank=best_sellers_rank,
                aplus_content=aplus_content,
                aplus_images=aplus_images,
                raw_html=raw_html,
            )

        except Exception as e:
            logger.error(f"解析产品 {asin} 时出错: {e}")
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

    async def _extract_hero_image(self) -> Optional[str]:
        """提取主图片URL - 委托给图片提取器"""
        return await self.image_extractor.extract_hero_image()

    async def _extract_gallery_images(self) -> List[Dict[str, Any]]:
        """提取画廊图片 - 委托给图片提取器"""
        return await self.image_extractor.extract_gallery_images()

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

    async def _extract_aplus_content(
        self, page: Page
    ) -> tuple[Optional[AplusContent], List[AplusImage]]:
        """Extract A+ content including brand story, FAQ, and product information"""
        try:
            logger.info("开始提取 A+ 内容和产品详细信息")

            # Extract brand story
            brand_story = await self._extract_brand_story(page)

            # Extract FAQ (if exists)
            faq = await self._extract_aplus_faq(page)

            # Extract product information from A+ content
            aplus_product_info = await self._extract_aplus_product_info(page)

            # Extract main product details
            main_product_details = await self._extract_product_details(page)

            # Combine product information from both sources
            product_information = {}
            if main_product_details:
                product_information.update(main_product_details)
            if aplus_product_info:
                product_information.update(aplus_product_info)

            # Use combined product information or None if empty
            final_product_info = product_information if product_information else None

            # Extract A+ images
            aplus_images = await self._extract_aplus_images(page)

            # Create AplusContent object if any content was found
            if brand_story or faq or final_product_info:
                aplus_content = AplusContent(
                    brand_story=brand_story,
                    faq=faq,
                    product_information=final_product_info,
                )
                logger.info(
                    f"Successfully extracted A+ content: brand_story={bool(brand_story)}, faq={bool(faq)}, product_info={bool(final_product_info)} (main_details={len(main_product_details) if main_product_details else 0}, aplus_info={len(aplus_product_info) if aplus_product_info else 0}), images={len(aplus_images)}"
                )
                return aplus_content, aplus_images
            else:
                logger.debug("No A+ content or product details found")
                return None, aplus_images

        except Exception as e:
            logger.error(f"Error extracting A+ content: {e}")
            return None, []

    async def _extract_brand_story(self, page: Page) -> Optional[str]:
        """Extract brand story from 'From the brand' section"""
        try:
            brand_story_parts = []

            # Method 1: Look for "From the brand" heading and extract following content
            try:
                # Find "From the brand" heading
                from_brand_elements = await page.query_selector_all("h2, h3, h4")
                for heading in from_brand_elements:
                    heading_text = await heading.text_content()
                    if heading_text and "from the brand" in heading_text.lower():
                        # Get the parent container
                        parent = await heading.evaluate("el => el.parentElement")
                        if parent:
                            # Extract text from siblings and children
                            text_elements = await parent.query_selector_all(
                                "p, div, span"
                            )
                            for elem in text_elements:
                                text = await elem.text_content()
                                if text:
                                    cleaned_text = " ".join(text.split()).strip()
                                    if (
                                        len(cleaned_text) > 15
                                        and cleaned_text not in brand_story_parts
                                    ):
                                        brand_story_parts.append(cleaned_text)
            except Exception as e:
                logger.debug(f"Error in method 1: {e}")

            # Method 2: Look for brand story specific containers
            try:
                brand_story_containers = await page.query_selector_all(
                    self.selectors["aplus_brand_story_container"]
                )
                for container in brand_story_containers:
                    # Extract text from brand story text selectors
                    text_elements = await container.query_selector_all(
                        self.selectors["aplus_brand_story_text"]
                    )
                    for text_elem in text_elements:
                        text = await text_elem.text_content()
                        if text:
                            cleaned_text = " ".join(text.split()).strip()
                            if (
                                len(cleaned_text) > 15
                                and cleaned_text not in brand_story_parts
                            ):
                                brand_story_parts.append(cleaned_text)

                    # Also extract from general text elements within the container
                    general_text_elements = await container.query_selector_all(
                        "p, h1, h2, h3, h4, h5, h6, div[class*='text'], span[class*='text']"
                    )
                    for elem in general_text_elements:
                        text = await elem.text_content()
                        if text:
                            cleaned_text = " ".join(text.split()).strip()
                            if (
                                len(cleaned_text) > 15
                                and cleaned_text not in brand_story_parts
                            ):
                                brand_story_parts.append(cleaned_text)
            except Exception as e:
                logger.debug(f"Error in method 2: {e}")

            # Method 3: Look for any A+ module that might contain brand story
            try:
                aplus_modules = await page.query_selector_all(
                    self.selectors["aplus_modules"]
                )
                for module in aplus_modules:
                    # Check if this module contains brand-related content
                    module_html = await module.inner_html()
                    if any(
                        keyword in module_html.lower()
                        for keyword in ["brand", "story", "about", "company"]
                    ):
                        text_elements = await module.query_selector_all(
                            "p, h1, h2, h3, h4, h5, h6, div[class*='text'], span[class*='text']"
                        )
                        for elem in text_elements:
                            text = await elem.text_content()
                            if text:
                                cleaned_text = " ".join(text.split()).strip()
                                if (
                                    len(cleaned_text) > 15
                                    and cleaned_text not in brand_story_parts
                                ):
                                    brand_story_parts.append(cleaned_text)
            except Exception as e:
                logger.debug(f"Error in method 3: {e}")

            if brand_story_parts:
                # Join all parts and clean up
                full_brand_story = " ".join(brand_story_parts)
                # Remove excessive whitespace and normalize
                full_brand_story = re.sub(r"\s+", " ", full_brand_story).strip()
                # Remove duplicated sentences
                sentences = full_brand_story.split(". ")
                unique_sentences = []
                for sentence in sentences:
                    if sentence.strip() and sentence.strip() not in unique_sentences:
                        unique_sentences.append(sentence.strip())
                full_brand_story = ". ".join(unique_sentences)

                logger.info(
                    f"Extracted brand story ({len(full_brand_story)} chars): {full_brand_story[:100]}..."
                )
                return full_brand_story

            logger.debug("No brand story content found")
            return None

        except Exception as e:
            logger.error(f"Error extracting brand story: {e}")
            return None

    async def _extract_aplus_faq(self, page: Page) -> Optional[List[Dict[str, str]]]:
        """Extract FAQ section from A+ content"""
        try:
            faq_items = []

            # Method 1: Look for dedicated FAQ containers
            try:
                faq_containers = await page.query_selector_all(
                    self.selectors["aplus_faq_container"]
                )
                for container in faq_containers:
                    questions = await container.query_selector_all(
                        self.selectors["aplus_faq_question"]
                    )
                    answers = await container.query_selector_all(
                        self.selectors["aplus_faq_answer"]
                    )

                    # Try to pair questions and answers
                    for i, question_elem in enumerate(questions):
                        question_text = await question_elem.text_content()
                        if question_text and i < len(answers):
                            answer_elem = answers[i]
                            answer_text = await answer_elem.text_content()

                            if answer_text:
                                question_clean = " ".join(question_text.split()).strip()
                                answer_clean = " ".join(answer_text.split()).strip()

                                if len(question_clean) > 5 and len(answer_clean) > 10:
                                    faq_items.append(
                                        {
                                            "question": question_clean,
                                            "answer": answer_clean,
                                        }
                                    )
            except Exception as e:
                logger.debug(f"Error in FAQ method 1: {e}")

            # Method 2: Look for definition lists (dt/dd pairs)
            try:
                dl_elements = await page.query_selector_all("dl")
                for dl in dl_elements:
                    # Check if this dl is within A+ content
                    aplus_parent = await dl.evaluate(
                        "el => el.closest('#aplus, .aplus-v2, [data-aplus-module]')"
                    )
                    if aplus_parent:
                        dt_elements = await dl.query_selector_all("dt")
                        dd_elements = await dl.query_selector_all("dd")

                        for i, dt in enumerate(dt_elements):
                            if i < len(dd_elements):
                                question_text = await dt.text_content()
                                answer_text = await dd_elements[i].text_content()

                                if question_text and answer_text:
                                    question_clean = " ".join(
                                        question_text.split()
                                    ).strip()
                                    answer_clean = " ".join(answer_text.split()).strip()

                                    if (
                                        len(question_clean) > 5
                                        and len(answer_clean) > 10
                                    ):
                                        faq_items.append(
                                            {
                                                "question": question_clean,
                                                "answer": answer_clean,
                                            }
                                        )
            except Exception as e:
                logger.debug(f"Error in FAQ method 2: {e}")

            # Method 3: Look for Q&A patterns in A+ modules
            try:
                aplus_modules = await page.query_selector_all(
                    self.selectors["aplus_modules"]
                )
                for module in aplus_modules:
                    module_text = await module.text_content()
                    if module_text and any(
                        keyword in module_text.lower()
                        for keyword in ["q:", "question", "faq", "frequently asked"]
                    ):
                        # Look for question-answer patterns
                        text_elements = await module.query_selector_all(
                            "p, h3, h4, h5, h6"
                        )
                        current_question = None

                        for elem in text_elements:
                            text = await elem.text_content()
                            if text:
                                text_clean = " ".join(text.split()).strip()

                                # Check if this looks like a question
                                if (
                                    text_clean.endswith("?")
                                    or text_clean.lower().startswith("q:")
                                    or text_clean.lower().startswith("question")
                                ):
                                    current_question = text_clean
                                elif current_question and len(text_clean) > 10:
                                    # This might be an answer
                                    faq_items.append(
                                        {
                                            "question": current_question,
                                            "answer": text_clean,
                                        }
                                    )
                                    current_question = None
            except Exception as e:
                logger.debug(f"Error in FAQ method 3: {e}")

            if faq_items:
                logger.info(f"Extracted {len(faq_items)} FAQ items")
                return faq_items

            logger.debug("No FAQ content found")
            return None

        except Exception as e:
            logger.error(f"Error extracting FAQ: {e}")
            return None

    async def _extract_product_details(self, page: Page) -> Optional[Dict[str, Any]]:
        """Extract product details from main product information tables"""
        try:
            product_details = {}

            # Method 1: Extract from main product details tables
            try:
                # Try multiple selectors for product details tables
                table_selectors = [
                    "#productDetails_detailBullets_sections1",
                    "#productDetails_techSpec_section_1",
                    ".prodDetTable",
                    "#detailBullets_feature_div table",
                ]

                for table_selector in table_selectors:
                    tables = await page.query_selector_all(table_selector)
                    for table in tables:
                        rows = await table.query_selector_all(
                            self.selectors["product_details_rows"]
                        )
                        for row in rows:
                            # Try to find key and value elements
                            key_elem = await row.query_selector(
                                self.selectors["product_details_key"]
                            )
                            value_elem = await row.query_selector(
                                self.selectors["product_details_value"]
                            )

                            if key_elem and value_elem:
                                key_text = await key_elem.text_content()
                                value_text = await value_elem.text_content()

                                if key_text and value_text:
                                    key_clean = " ".join(key_text.split()).strip()
                                    value_clean = " ".join(value_text.split()).strip()

                                    # Filter out empty or too short values
                                    if len(key_clean) > 1 and len(value_clean) > 1:
                                        # Clean up common artifacts
                                        key_clean = key_clean.replace(":", "").strip()
                                        product_details[key_clean] = value_clean
            except Exception as e:
                logger.debug(f"Error in product details method 1: {e}")

            # Method 2: Extract from detail bullets feature div (alternative layout)
            try:
                detail_bullets = await page.query_selector_all(
                    "#detailBullets_feature_div ul li"
                )
                for bullet in detail_bullets:
                    text = await bullet.text_content()
                    if text and ":" in text:
                        text_clean = " ".join(text.split()).strip()
                        if text_clean.count(":") == 1:
                            key, value = text_clean.split(":", 1)
                            key = key.strip()
                            value = value.strip()

                            if len(key) > 1 and len(value) > 1 and len(key) < 100:
                                product_details[key] = value
            except Exception as e:
                logger.debug(f"Error in product details method 2: {e}")

            # Method 3: Extract from any table with product detail classes
            try:
                # Look for tables with product detail specific classes
                detail_tables = await page.query_selector_all(
                    "table.a-keyvalue, table.prodDetTable"
                )
                for table in detail_tables:
                    rows = await table.query_selector_all("tr")
                    for row in rows:
                        cells = await row.query_selector_all("td, th")
                        if len(cells) >= 2:
                            key_elem = cells[0]
                            value_elem = cells[1]

                            key_text = await key_elem.text_content()
                            value_text = await value_elem.text_content()

                            if key_text and value_text:
                                key_clean = " ".join(key_text.split()).strip()
                                value_clean = " ".join(value_text.split()).strip()

                                if len(key_clean) > 1 and len(value_clean) > 1:
                                    key_clean = key_clean.replace(":", "").strip()
                                    product_details[key_clean] = value_clean
            except Exception as e:
                logger.debug(f"Error in product details method 3: {e}")

            if product_details:
                logger.info(f"Extracted {len(product_details)} product detail items")
                return product_details

            logger.debug("No product details found")
            return None

        except Exception as e:
            logger.error(f"Error extracting product details: {e}")
            return None

    async def _extract_aplus_product_info(self, page: Page) -> Optional[Dict[str, Any]]:
        """Extract product information from A+ content"""
        try:
            product_info = {}

            # Method 1: Extract from comparison tables and structured data
            try:
                table_containers = await page.query_selector_all(
                    self.selectors["aplus_table_container"]
                )
                for table in table_containers:
                    rows = await table.query_selector_all(
                        self.selectors["aplus_table_rows"]
                    )
                    for row in rows:
                        cells = await row.query_selector_all(
                            self.selectors["aplus_table_cells"]
                        )
                        if len(cells) >= 2:
                            key_elem = cells[0]
                            value_elem = cells[1]

                            key_text = await key_elem.text_content()
                            value_text = await value_elem.text_content()

                            if key_text and value_text:
                                key_clean = " ".join(key_text.split()).strip()
                                value_clean = " ".join(value_text.split()).strip()

                                if len(key_clean) > 2 and len(value_clean) > 2:
                                    product_info[key_clean] = value_clean
            except Exception as e:
                logger.debug(f"Error in product info method 1: {e}")

            # Method 2: Extract key-value pairs from A+ modules
            try:
                aplus_modules = await page.query_selector_all(
                    self.selectors["aplus_modules"]
                )
                for module in aplus_modules:
                    # Look for patterns like "Feature: Value" or "Specification: Detail"
                    text_elements = await module.query_selector_all("p, div, span")
                    for elem in text_elements:
                        text = await elem.text_content()
                        if text and ":" in text:
                            text_clean = " ".join(text.split()).strip()
                            if text_clean.count(":") == 1:  # Simple key:value pattern
                                key, value = text_clean.split(":", 1)
                                key = key.strip()
                                value = value.strip()

                                if len(key) > 2 and len(value) > 2 and len(key) < 50:
                                    product_info[key] = value
            except Exception as e:
                logger.debug(f"Error in product info method 2: {e}")

            # Method 3: Extract from structured content with specific classes
            try:
                key_elements = await page.query_selector_all(
                    ".apm-tablemodule-keyhead, .product-key, .spec-key"
                )
                value_elements = await page.query_selector_all(
                    ".apm-tablemodule-valuecell, .product-value, .spec-value"
                )

                # Try to pair keys and values by position
                min_length = min(len(key_elements), len(value_elements))
                for i in range(min_length):
                    key_text = await key_elements[i].text_content()
                    value_text = await value_elements[i].text_content()

                    if key_text and value_text:
                        key_clean = " ".join(key_text.split()).strip()
                        value_clean = " ".join(value_text.split()).strip()

                        if len(key_clean) > 2 and len(value_clean) > 2:
                            product_info[key_clean] = value_clean
            except Exception as e:
                logger.debug(f"Error in product info method 3: {e}")

            if product_info:
                logger.info(f"Extracted {len(product_info)} product information items")
                return product_info

            logger.debug("No product information found")
            return None

        except Exception as e:
            logger.error(f"Error extracting product information: {e}")
            return None

    async def _extract_aplus_images(self, page: Page) -> List[AplusImage]:
        """Extract images from A+ content"""
        try:
            aplus_images = []
            position = 0

            # Extract images from A+ content using the selector
            image_elements = await page.query_selector_all(
                self.selectors["aplus_images"]
            )

            for img_element in image_elements:
                try:
                    # Get image URL - A+ images are already high resolution
                    img_url = await self._get_aplus_image_url(img_element)

                    if not img_url:
                        continue

                    # Skip very small images (icons, spacers, etc.)
                    if await self._should_skip_aplus_image(img_element):
                        continue

                    # Determine content section based on parent elements
                    content_section = await self._determine_aplus_image_context(
                        img_element
                    )

                    # Create AplusImage object
                    aplus_image = AplusImage(
                        original_url=img_url,
                        role=content_section,
                        position=position,
                        status=AplusImageStatusEnum.PENDING,
                    )

                    aplus_images.append(aplus_image)
                    position += 1

                except Exception as e:
                    logger.debug(f"Error processing A+ image: {e}")
                    continue

            logger.info(f"Extracted {len(aplus_images)} A+ images")
            return aplus_images

        except Exception as e:
            logger.error(f"Error extracting A+ images: {e}")
            return []

    async def _get_aplus_image_url(self, element) -> Optional[str]:
        """Get A+ image URL - A+ images are already high resolution"""
        try:
            # Priority order for A+ image URLs
            url_attributes = ["src", "data-src", "data-lazy-src", "data-original"]

            for attr in url_attributes:
                img_url = await element.get_attribute(attr)
                if img_url:
                    # Clean up URL (remove query parameters if needed)
                    if "?" in img_url and "amazon" in img_url:
                        img_url = img_url.split("?")[0]
                    return img_url

            return None

        except Exception as e:
            logger.debug(f"Error getting A+ image URL: {e}")
            return None

    async def _should_skip_aplus_image(self, img_element) -> bool:
        """Determine if A+ image should be skipped based on size and other criteria"""
        try:
            # Check computed style dimensions
            try:
                computed_width = await img_element.evaluate(
                    "el => getComputedStyle(el).width"
                )
                computed_height = await img_element.evaluate(
                    "el => getComputedStyle(el).height"
                )
                if computed_width and computed_height:
                    w = float(computed_width.replace("px", ""))
                    h = float(computed_height.replace("px", ""))
                    if w < 50 or h < 50:
                        return True
            except:
                pass

            # Check if image is hidden
            try:
                is_visible = await img_element.evaluate(
                    "el => getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden'"
                )
                if not is_visible:
                    return True
            except:
                pass

            return False

        except Exception as e:
            logger.debug(f"Error checking if A+ image should be skipped: {e}")
            return False

    async def _determine_aplus_image_context(self, img_element) -> str:
        """Determine content section based on parent elements"""
        try:
            content_section = "aplus_detail"  # default

            # Check if it's in brand story section
            brand_story_parent = await img_element.evaluate(
                "el => el.closest('.apm-brand-story-hero, .apm-brand-story-card, .brand-story-hero, .brand-story-card, [data-aplus-module*=\"brand\"]')"
            )
            if brand_story_parent:
                content_section = "brand_story"
                return content_section

            # Check if it's a comparison or table image
            table_parent = await img_element.evaluate(
                'el => el.closest(\'.apm-tablemodule, .comparison-table, [data-aplus-module*="table"], [data-aplus-module*="comparison"]\')'
            )
            if table_parent:
                content_section = "product_info"
                return content_section

            # Check parent classes for more specific categorization
            parent_classes = await img_element.evaluate(
                "el => el.closest('[class]')?.className || ''"
            )

            if parent_classes:
                parent_classes_lower = parent_classes.lower()

                # Lifestyle or scene images
                if any(
                    keyword in parent_classes_lower
                    for keyword in ["lifestyle", "scene", "hero"]
                ):
                    content_section = "brand_story"
                # Infographic images
                elif any(
                    keyword in parent_classes_lower
                    for keyword in ["infographic", "info", "chart"]
                ):
                    content_section = "product_info"
                # FAQ section images
                elif any(
                    keyword in parent_classes_lower
                    for keyword in ["faq", "question", "answer"]
                ):
                    content_section = "faq"

            return content_section

        except Exception as e:
            logger.debug(f"Error determining A+ image context: {e}")
            return "aplus_detail"
