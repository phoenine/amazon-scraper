import re
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any, Set
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class AmazonImageExtractor:
    """Amazon图片提取器 - 专门处理Amazon产品页面的图片提取"""

    def __init__(self, page: Page, selectors: Dict[str, str]):
        self.page = page
        self.selectors = selectors

    async def extract_hero_image(self) -> Optional[str]:
        """提取主图片URL"""
        try:
            hero_element = await self.page.query_selector(self.selectors["hero_image"])
            if not hero_element:
                logger.warning("未找到主图片元素")
                return None

            # 尝试获取高分辨率URL
            data_old_hires = await hero_element.get_attribute("data-old-hires")
            if data_old_hires:
                return data_old_hires

            # 尝试从data-a-dynamic-image获取最大分辨率
            data_dynamic = await hero_element.get_attribute("data-a-dynamic-image")
            if data_dynamic:
                url = self._extract_largest_from_dynamic_image(data_dynamic)
                if url:
                    return url

            # 回退到src属性
            src = await hero_element.get_attribute("src")
            if src:
                return self._convert_to_high_resolution(src)

            return None

        except Exception as e:
            logger.error(f"提取主图片时出错: {e}")
            return None

    async def extract_gallery_images(self) -> List[Dict[str, Any]]:
        """提取画廊图片"""
        images = []
        seen_urls = set()

        try:
            carousel_images = await self._extract_carousel_images()
            for img in carousel_images:
                if img["url"] not in seen_urls:
                    images.append(img)
                    seen_urls.add(img["url"])

            # 如果交互式提取失败，回退到静态提取
            if len(images) <= 1:
                static_images = await self._extract_static_gallery()
                for img in static_images:
                    if img["url"] not in seen_urls:
                        images.append(img)
                        seen_urls.add(img["url"])

            # 重新分配position
            for i, img in enumerate(images):
                img["position"] = i

            logger.info(f"成功提取 {len(images)} 张图片")
            return images

        except Exception as e:
            logger.error(f"提取画廊图片时出错: {e}")
            return []

    async def _extract_carousel_images(self) -> List[Dict[str, Any]]:
        """提取主轮播中的图片"""
        images = []
        try:
            carousel_imgs = await self.page.query_selector_all(
                self.selectors["gallery_images"]
            )

            for i, img_element in enumerate(carousel_imgs):
                url = await self._extract_high_res_url_from_element(img_element)

                if url:
                    images.append(
                        {
                            "url": url,
                            "position": i + 1,
                            "role": "gallery",
                        }
                    )
            logger.info(f"从主轮播提取到 {len(images)} 张图片")
            return images

        except Exception as e:
            logger.error(f"提取主轮播图片时出错: {e}")
            return []

    async def _extract_static_gallery(self) -> List[Dict[str, Any]]:
        """静态提取画廊图片（回退方案）"""
        images = []
        try:
            # 使用配置的选择器
            img_elements = await self.page.query_selector_all(
                self.selectors["gallery_images"]
            )

            for i, img_element in enumerate(img_elements):
                src = await img_element.get_attribute("src")
                if src:
                    high_res_url = self._convert_to_high_resolution(src)
                    images.append(
                        {"url": high_res_url, "position": i + 1, "role": "gallery"}
                    )

            logger.info(f"静态提取到 {len(images)} 张图片")
            return images

        except Exception as e:
            logger.error(f"静态画廊提取失败: {e}")
            return []

    def _extract_largest_from_dynamic_image(self, data_dynamic: str) -> Optional[str]:
        """从data-a-dynamic-image中提取最大分辨率的图片URL"""
        try:
            # data-a-dynamic-image格式: {"url1":[width1,height1],"url2":[width2,height2]}
            image_data = json.loads(data_dynamic)

            max_resolution = 0
            best_url = None

            for url, dimensions in image_data.items():
                if len(dimensions) >= 2:
                    resolution = dimensions[0] * dimensions[1]  # width * height
                    if resolution > max_resolution:
                        max_resolution = resolution
                        best_url = url

            return best_url

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"解析data-a-dynamic-image失败: {e}")
            return None

    def _convert_to_high_resolution(self, url: str) -> str:
        """将图片URL转换为高分辨率版本"""
        if not url:
            return url

        patterns = [
            # 处理 _AC_SX466_ 类型的URL，转换为 _AC_SL1500_ (高分辨率)
            (r"\._AC_SX\d+_\.", "._AC_SL1500_."),
            (r"\._AC_SY\d+_\.", "._AC_SL1500_."),
            (r"\._AC_US\d+_\.", "._AC_SL1500_."),
            # 原有的模式
            (r"\._[A-Z]{2}\d+_\.", "."),  # ._SX300_. -> .
            (r"\._[A-Z]{2}\d+,\d+_\.", "."),  # ._SX300,300_. -> .
            (r"\._[A-Z]{2}\d+[A-Z]{2}\d+_\.", "."),  # ._SX300SY300_. -> .
        ]

        result_url = url
        for pattern, replacement in patterns:
            result_url = re.sub(pattern, replacement, result_url)

        return result_url

    async def _extract_high_res_url_from_element(self, element) -> Optional[str]:
        """从元素中提取高分辨率图片URL"""
        try:
            # 优先级1: data-old-hires (通常是最高分辨率)
            data_old_hires = await element.get_attribute("data-old-hires")
            if data_old_hires:
                return data_old_hires

            # 优先级2: data-a-dynamic-image中的最大分辨率
            data_dynamic = await element.get_attribute("data-a-dynamic-image")
            if data_dynamic:
                url = self._extract_largest_from_dynamic_image(data_dynamic)
                if url:
                    return url

            # 优先级3: src属性，转换为高分辨率
            src = await element.get_attribute("src")
            if src:
                return self._convert_to_high_resolution(src)

            return None

        except Exception as e:
            logger.warning(f"提取高分辨率URL时出错: {e}")
            return None
