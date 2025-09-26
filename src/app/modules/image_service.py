import asyncio
import aiohttp
import hashlib
import os
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from pathlib import Path

from ..config import settings
from .models import ScrapedProduct


class ImageService:
    """图片下载和存储服务"""

    def __init__(self, db_service):
        self.db_service = db_service
        self.session = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        # 创建aiohttp session
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def download_and_store_images(
        self, product_id: str, scraped_data: ScrapedProduct
    ) -> Dict[str, Any]:
        """下载并存储产品的所有图片"""
        results = {
            "hero_image": None,
            "gallery_images": [],
            "aplus_images": [],  # 新增A+图片结果
            "errors": [],
        }

        try:
            # 下载主图
            if scraped_data.hero_image_url:
                hero_result = await self._download_and_upload_image(
                    scraped_data.hero_image_url,
                    scraped_data.asin,
                    scraped_data.marketplace,
                    "hero",
                    0,
                )

                if hero_result["success"]:
                    results["hero_image"] = hero_result
                else:
                    results["errors"].append(
                        f"Hero image download failed: {hero_result['error']}"
                    )

            # 下载轮播图
            if scraped_data.gallery_images:
                for i, gallery_item in enumerate(scraped_data.gallery_images):
                    # 修复：从字典中提取URL
                    if isinstance(gallery_item, dict):
                        gallery_url = gallery_item.get("url")
                        position = gallery_item.get("position", i + 1)
                    else:
                        # 如果是字符串，直接使用
                        gallery_url = gallery_item
                        position = i + 1

                    if not gallery_url:
                        results["errors"].append(f"Gallery image {i+1}: No URL found")
                        continue

                    gallery_result = await self._download_and_upload_image(
                        gallery_url,
                        scraped_data.asin,
                        scraped_data.marketplace,
                        "gallery",
                        position,
                    )

                    if gallery_result["success"]:
                        results["gallery_images"].append(gallery_result)
                    else:
                        results["errors"].append(
                            f"Gallery image {i+1} download failed: {gallery_result['error']}"
                        )

            # 下载A+图片
            if scraped_data.aplus_images:
                for aplus_img in scraped_data.aplus_images:
                    aplus_result = await self._download_and_upload_aplus_image(
                        aplus_img,
                        scraped_data.asin,
                        scraped_data.marketplace,
                    )

                    if aplus_result["success"]:
                        results["aplus_images"].append(aplus_result)
                    else:
                        results["errors"].append(
                            f"A+ image download failed: {aplus_result['error']}"
                        )

            # 更新数据库中的storage_path
            await self._update_image_storage_paths(product_id, results)

        except Exception as e:
            results["errors"].append(f"General error: {str(e)}")

        return results

    async def _download_and_upload_aplus_image(
        self, aplus_img, asin: str, marketplace: str
    ) -> Dict[str, Any]:
        """下载A+图片并上传到Supabase Storage"""
        try:
            # 下载图片
            image_data = await self._download_image(aplus_img.original_url)
            if not image_data:
                return {"success": False, "error": "Failed to download A+ image"}

            # 生成存储路径
            file_extension = self._get_file_extension(aplus_img.original_url)
            etag = hashlib.md5(image_data).hexdigest()[:8]

            # A+图片路径格式: aplus_{section}_{position}_{etag}.jpg
            section = aplus_img.content_section or "unknown"
            storage_path = f"{marketplace}/{asin}/aplus_{section}_{aplus_img.position}_{etag}{file_extension}"

            # 上传到Supabase Storage
            upload_success = await self._upload_to_supabase_storage(
                storage_path, image_data
            )

            if upload_success:
                return {
                    "success": True,
                    "storage_path": storage_path,
                    "original_url": aplus_img.original_url,
                    "content_section": aplus_img.content_section,
                    "position": aplus_img.position,
                    "size": len(image_data),
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to upload A+ image to storage",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _download_and_upload_image(
        self, image_url: str, asin: str, marketplace: str, role: str, position: int
    ) -> Dict[str, Any]:
        """下载单个图片并上传到Supabase Storage"""
        try:
            # 下载图片
            image_data = await self._download_image(image_url)
            if not image_data:
                return {"success": False, "error": "Failed to download image"}

            # 生成存储路径
            file_extension = self._get_file_extension(image_url)
            etag = hashlib.md5(image_data).hexdigest()[:8]

            if role == "hero":
                storage_path = f"{marketplace}/{asin}/hero_{etag}{file_extension}"
            elif role == "gallery":
                storage_path = (
                    f"{marketplace}/{asin}/gallery_{position}_{etag}{file_extension}"
                )
            else:
                # 其他类型图片的默认处理
                storage_path = (
                    f"{marketplace}/{asin}/{role}_{position}_{etag}{file_extension}"
                )

            # 上传到Supabase Storage
            upload_success = await self._upload_to_supabase_storage(
                storage_path, image_data
            )

            if upload_success:
                return {
                    "success": True,
                    "storage_path": storage_path,
                    "original_url": image_url,
                    "role": role,
                    "position": position,
                    "size": len(image_data),
                }
            else:
                return {"success": False, "error": "Failed to upload to storage"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _download_image(self, url: str) -> Optional[bytes]:
        """下载图片数据"""
        try:
            # 转换为高分辨率URL
            high_res_url = self._get_high_resolution_url(url)

            async with self.session.get(high_res_url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    # 如果高分辨率URL失败，尝试原始URL
                    if high_res_url != url:
                        async with self.session.get(url) as fallback_response:
                            if fallback_response.status == 200:
                                return await fallback_response.read()
                    return None

        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            return None

    def _get_high_resolution_url(self, url: str) -> str:
        """将Amazon图片URL转换为高分辨率版本"""
        try:
            # Amazon图片URL通常包含尺寸参数，我们可以替换为更大的尺寸
            # 例如：https://m.media-amazon.com/images/I/71abc123._AC_SL1500_.jpg
            # 可以替换为：https://m.media-amazon.com/images/I/71abc123._AC_SL2000_.jpg

            if "amazon" in url and "._AC_" in url:
                # 替换为更大的尺寸
                url = url.replace("._AC_SL1500_", "._AC_SL2000_")
                url = url.replace("._AC_SL1000_", "._AC_SL2000_")
                url = url.replace("._AC_SL500_", "._AC_SL2000_")
                url = url.replace("._AC_SX", "._AC_SL2000_")
                url = url.replace("._AC_SY", "._AC_SL2000_")

                # 如果没有尺寸参数，添加高分辨率参数
                if "._AC_" in url and not any(x in url for x in ["_SL", "_SX", "_SY"]):
                    url = url.replace("._AC_", "._AC_SL2000_")

            return url

        except Exception:
            return url

    def _get_file_extension(self, url: str) -> str:
        """从URL获取文件扩展名"""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()

            # 常见的图片扩展名
            if ".jpg" in path or ".jpeg" in path:
                return ".jpg"
            elif ".png" in path:
                return ".png"
            elif ".webp" in path:
                return ".webp"
            elif ".gif" in path:
                return ".gif"
            else:
                # 默认使用jpg
                return ".jpg"
        except Exception:
            return ".jpg"

    def _get_content_type(self, file_extension: str) -> str:
        """根据文件扩展名获取content-type"""
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        return content_types.get(file_extension.lower(), "image/jpeg")

    async def _upload_to_supabase_storage(
        self, storage_path: str, image_data: bytes
    ) -> bool:
        """上传图片到Supabase Storage"""
        try:
            # 获取文件扩展名和content-type
            file_extension = Path(storage_path).suffix
            content_type = self._get_content_type(file_extension)

            # 使用Supabase客户端上传文件
            result = self.db_service.client.storage.from_(
                settings.STORAGE_BUCKET
            ).upload(
                path=storage_path,
                file=image_data,
                file_options={
                    "content-type": content_type,
                    "upsert": "true",  # 修复：使用字符串而不是布尔值
                },
            )

            # 检查上传结果
            if hasattr(result, "error") and result.error:
                print(f"Storage upload error: {result.error}")
                return False

            return True

        except Exception as e:
            print(f"Error uploading to storage: {e}")
            return False

    async def _update_product_hero_image_path(self, product_id: str, storage_path: str):
        """更新产品表中的hero_image_path"""
        try:
            self.db_service.client.table("amazon_products").update(
                {"hero_image_path": storage_path}
            ).eq("id", product_id).execute()
        except Exception as e:
            print(f"Error updating hero image path: {e}")

    async def _update_image_storage_paths(
        self, product_id: str, results: Dict[str, Any]
    ):
        """更新数据库中的图片存储路径"""
        try:
            # 更新主图路径
            if results["hero_image"]:
                await self._update_product_hero_image_path(
                    product_id, results["hero_image"]["storage_path"]
                )

            # 更新轮播图路径
            for gallery_image in results["gallery_images"]:
                # 查找对应的图片记录并更新storage_path
                self.db_service.client.table("amazon_product_images").update(
                    {"storage_path": gallery_image["storage_path"]}
                ).eq("product_id", product_id).eq(
                    "original_url", gallery_image["original_url"]
                ).execute()

            # 更新A+图片路径
            for aplus_image in results["aplus_images"]:
                self.db_service.client.table("amazon_aplus_images").update(
                    {"storage_path": aplus_image["storage_path"], "status": "stored"}
                ).eq("product_id", product_id).eq(
                    "original_url", aplus_image["original_url"]
                ).execute()

        except Exception as e:
            print(f"Error updating image storage paths: {e}")
