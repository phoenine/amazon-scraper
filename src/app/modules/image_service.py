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
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()

    async def download_and_store_images(
        self, product_id: str, scraped_data: ScrapedProduct
    ) -> Dict[str, Any]:
        """下载并存储产品图片到Supabase Storage"""
        results = {"hero_image": None, "gallery_images": [], "errors": []}

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
                    # 更新产品表的hero_image_path
                    await self._update_product_hero_image_path(
                        product_id, hero_result["storage_path"]
                    )
                else:
                    results["errors"].append(
                        f"Hero image download failed: {hero_result['error']}"
                    )

            # 下载轮播图
            for i, img_data in enumerate(scraped_data.gallery_images):
                if isinstance(img_data, dict) and "url" in img_data:
                    img_url = img_data["url"]
                elif isinstance(img_data, str):
                    img_url = img_data
                else:
                    continue

                gallery_result = await self._download_and_upload_image(
                    img_url,
                    scraped_data.asin,
                    scraped_data.marketplace,
                    "gallery",
                    i + 1,
                )

                if gallery_result["success"]:
                    results["gallery_images"].append(gallery_result)
                else:
                    results["errors"].append(
                        f"Gallery image {i+1} download failed: {gallery_result['error']}"
                    )

            # 更新数据库中的storage_path
            await self._update_image_storage_paths(product_id, results)

        except Exception as e:
            results["errors"].append(f"General error: {str(e)}")

        return results

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
            else:
                storage_path = (
                    f"{marketplace}/{asin}/gallery_{position}_{etag}{file_extension}"
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
            # 处理Amazon图片URL，获取高清版本
            high_res_url = self._get_high_resolution_url(url)

            async with self.session.get(high_res_url) as response:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    if content_type.startswith("image/"):
                        return await response.read()
                    else:
                        # 如果不是图片，尝试原始URL
                        async with self.session.get(url) as fallback_response:
                            if fallback_response.status == 200:
                                return await fallback_response.read()
                return None
        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            return None

    def _get_high_resolution_url(self, url: str) -> str:
        """将Amazon图片URL转换为高清版本"""
        # Amazon图片URL模式替换
        replacements = [
            ("_SS40_", "_SL1500_"),
            ("_SS50_", "_SL1500_"),
            ("_SS75_", "_SL1500_"),
            ("_SS100_", "_SL1500_"),
            ("_SS200_", "_SL1500_"),
            ("_SS300_", "_SL1500_"),
            ("_AC_SX40_", "_AC_SL1500_"),
            ("_AC_SX50_", "_AC_SL1500_"),
            ("_AC_SX75_", "_AC_SL1500_"),
            ("_AC_SX100_", "_AC_SL1500_"),
            ("_AC_SX200_", "_AC_SL1500_"),
            ("_AC_SX300_", "_AC_SL1500_"),
        ]

        high_res_url = url
        for old, new in replacements:
            if old in high_res_url:
                high_res_url = high_res_url.replace(old, new)
                break

        return high_res_url

    def _get_file_extension(self, url: str) -> str:
        """从URL获取文件扩展名"""
        parsed = urlparse(url)
        path = parsed.path.lower()

        if path.endswith(".jpg") or path.endswith(".jpeg"):
            return ".jpg"
        elif path.endswith(".png"):
            return ".png"
        elif path.endswith(".webp"):
            return ".webp"
        else:
            return ".jpg"  # 默认使用jpg

    async def _upload_to_supabase_storage(
        self, storage_path: str, image_data: bytes
    ) -> bool:
        """上传图片到Supabase Storage"""
        try:
            # 使用Supabase客户端上传文件
            result = self.db_service.client.storage.from_(
                settings.STORAGE_BUCKET
            ).upload(
                path=storage_path,
                file=image_data,
                file_options={
                    "content-type": "image/jpeg",
                    "upsert": True,  # 如果文件已存在则覆盖
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
        """更新图片表中的storage_path字段"""
        try:
            # 更新主图
            if results["hero_image"] and results["hero_image"]["success"]:
                self.db_service.client.table("amazon_product_images").update(
                    {"storage_path": results["hero_image"]["storage_path"]}
                ).eq("product_id", product_id).eq("role", "hero").execute()

            # 更新轮播图
            for gallery_img in results["gallery_images"]:
                if gallery_img["success"]:
                    self.db_service.client.table("amazon_product_images").update(
                        {"storage_path": gallery_img["storage_path"]}
                    ).eq("product_id", product_id).eq("role", "gallery").eq(
                        "position", gallery_img["position"]
                    ).execute()

        except Exception as e:
            print(f"Error updating image storage paths: {e}")
