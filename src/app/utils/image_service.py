import asyncio
import aiohttp
import hashlib
import os
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from pathlib import Path

from ..config import settings
from ..modules.models import ScrapedProduct


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
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()

    async def download_and_store_images(
        self, product_id: str, scraped_data: ScrapedProduct
    ) -> Dict[str, Any]:
        """下载并存储产品的所有图片"""
        results = {
            "hero_image": None,
            "gallery_images": [],
            "aplus_images": [],
            "errors": [],
        }

        # 获取产品的ETag用于文件名
        etag = self._calculate_etag_short(scraped_data)

        # 下载主图片
        if scraped_data.hero_image_url:
            hero_result = await self._download_and_upload_image(
                scraped_data.hero_image_url,
                scraped_data.asin,
                scraped_data.marketplace,
                "hero",
                0,
                etag,  # 传入ETag
            )
            if hero_result["success"]:
                results["hero_image"] = hero_result
                # 更新产品的主图片路径
                await self._update_product_hero_image_path(
                    product_id, hero_result["storage_path"]
                )
            else:
                results["errors"].append(
                    f"Failed to download hero image: {hero_result.get('error', 'Unknown error')}"
                )

        # 下载画廊图片
        for i, gallery_img in enumerate(scraped_data.gallery_images):
            # 跳过hero图片，因为已经单独处理了
            if gallery_img.get("role") == "hero":
                continue

            gallery_result = await self._download_and_upload_image(
                gallery_img["url"],
                scraped_data.asin,
                scraped_data.marketplace,
                "gallery",  # 统一使用 "gallery"
                i,  # 使用 i，从0开始，与 store.py 保持一致
                etag,  # 传入ETag
            )
            if gallery_result["success"]:
                results["gallery_images"].append(gallery_result)
            else:
                results["errors"].append(
                    f"Failed to download gallery image {i}: {gallery_result.get('error', 'Unknown error')}"
                )

        # 下载A+内容图片
        for aplus_img in scraped_data.aplus_images:
            aplus_result = await self._download_and_upload_aplus_image(
                aplus_img, scraped_data.asin, scraped_data.marketplace, etag
            )
            if aplus_result["success"]:
                results["aplus_images"].append(aplus_result)
            else:
                results["errors"].append(
                    f"Failed to download A+ image: {aplus_result.get('error', 'Unknown error')}"
                )

        # 批量更新图片存储路径
        await self._update_image_storage_paths(product_id, results)

        return results

    async def _download_and_upload_aplus_image(
        self, aplus_img, asin: str, marketplace: str, etag: str
    ) -> Dict[str, Any]:
        """下载并上传A+内容图片"""
        try:
            image_url = aplus_img.original_url
            if not image_url:
                return {"success": False, "error": "缺少图片URL"}

            # 下载图片
            image_data = await self._download_image(image_url)
            if not image_data:
                return {"success": False, "error": "图片下载失败"}

            # 生成存储路径 - 包含ETag
            file_extension = self._get_file_extension(image_url)
            filename = f"aplus_{aplus_img.position}_{etag}{file_extension}"
            storage_path = f"{marketplace}/{asin}/aplus/{filename}"

            # 清理旧文件并上传新文件
            upload_success = await self._upload_with_cleanup(
                storage_path,
                image_data,
                asin,
                marketplace,
                "aplus",
                aplus_img.position,
            )

            if upload_success:
                return {
                    "success": True,
                    "storage_path": storage_path,
                    "original_url": image_url,
                    "position": aplus_img.position,
                }
            else:
                return {
                    "success": False,
                    "error": "上传到存储失败",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"处理A+图片时出错: {str(e)}",
            }

    async def _download_and_upload_image(
        self,
        image_url: str,
        asin: str,
        marketplace: str,
        role: str,
        position: int,
        etag: str,
    ) -> Dict[str, Any]:
        """下载并上传单个图片"""
        try:
            # 转换为高分辨率URL
            high_res_url = self._get_high_resolution_url(image_url)

            # 下载图片
            image_data = await self._download_image(high_res_url)
            if not image_data:
                return {"success": False, "error": "图片下载失败"}

            file_extension = self._get_file_extension(high_res_url)
            if role == "hero":
                filename = f"{role}_{etag}{file_extension}"
            else:
                filename = f"{role}_{position}_{etag}{file_extension}"
            storage_path = f"{marketplace}/{asin}/{filename}"

            # 清理旧文件并上传新文件
            upload_success = await self._upload_with_cleanup(
                storage_path, image_data, asin, marketplace, role, position
            )

            if upload_success:
                return {
                    "success": True,
                    "storage_path": storage_path,
                    "original_url": image_url,
                    "high_res_url": high_res_url,
                    "role": role,
                    "position": position,
                }
            else:
                return {
                    "success": False,
                    "error": "上传到存储失败",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"处理图片时出错: {str(e)}",
            }

    async def _download_image(self, url: str) -> Optional[bytes]:
        """下载图片数据"""
        try:
            if not self.session:
                raise Exception("HTTP session未初始化")

            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    print(f"下载图片失败，状态码: {response.status}, URL: {url}")
                    return None

        except asyncio.TimeoutError:
            print(f"下载图片超时: {url}")
            return None
        except Exception as e:
            print(f"下载图片时出错: {e}, URL: {url}")
            return None

    def _get_high_resolution_url(self, url: str) -> str:
        """将Amazon图片URL转换为高分辨率版本"""
        if not url:
            return url

        # Amazon图片URL模式
        # 例如: https://m.media-amazon.com/images/I/71abc123._SX300_.jpg
        # 转换为: https://m.media-amazon.com/images/I/71abc123.jpg

        # 移除尺寸限制参数
        import re

        patterns = [
            r"\._[A-Z]{2}\d+_\.",  # ._SX300_.
            r"\._[A-Z]{2}\d+,\d+_\.",  # ._SX300,300_.
            r"\._[A-Z]{2}\d+[A-Z]{2}\d+_\.",  # ._SX300SY300_.
        ]

        result_url = url
        for pattern in patterns:
            result_url = re.sub(pattern, ".", result_url)

        return result_url

    def _get_file_extension(self, url: str) -> str:
        """从URL中提取文件扩展名"""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path

            # 移除查询参数和片段
            if "?" in path:
                path = path.split("?")[0]

            # 获取扩展名
            _, ext = os.path.splitext(path)

            # 如果没有扩展名，默认使用.jpg
            if not ext:
                ext = ".jpg"

            return ext.lower()
        except Exception:
            return ".jpg"

    def _get_content_type(self, file_extension: str) -> str:
        """根据文件扩展名获取Content-Type"""
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return content_types.get(file_extension.lower(), "image/jpeg")

    async def _upload_to_supabase_storage(
        self, storage_path: str, image_data: bytes
    ) -> bool:
        """上传图片到Supabase Storage"""
        try:
            from supabase import create_client

            supabase = create_client(
                settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
            )

            # 获取文件扩展名用于Content-Type
            file_extension = self._get_file_extension(storage_path)
            content_type = self._get_content_type(file_extension)

            # 直接上传文件
            response = supabase.storage.from_(settings.STORAGE_BUCKET).upload(
                storage_path, image_data, {"content-type": content_type}
            )

            # 检查是否成功
            if hasattr(response, "error") and response.error:
                # 检查是否是重复文件错误
                error_str = str(response.error)
                if (
                    "already exists" in error_str
                    or "Duplicate" in error_str
                    or "409" in error_str
                ):
                    print(f"文件已存在，视为成功: {storage_path}")
                    return True
                else:
                    print(f"上传到Supabase Storage失败: {response.error}")
                    return False

            print(f"成功上传图片到: {storage_path}")
            return True

        except Exception as e:
            # 检查异常中是否包含409错误信息
            error_str = str(e)
            if (
                "409" in error_str
                or "Duplicate" in error_str
                or "already exists" in error_str
            ):
                print(f"文件已存在（异常处理），视为成功: {storage_path}")
                return True
            else:
                print(f"上传到Supabase Storage时出错: {e}")
                return False

    async def _update_product_hero_image_path(self, product_id: str, storage_path: str):
        """更新产品的主图片存储路径"""
        try:
            # 更新amazon_product_images表中role='hero'的记录
            self.db_service.client.table("amazon_product_images").update(
                {"storage_path": storage_path}
            ).eq("product_id", product_id).eq("role", "hero").execute()
        except Exception as e:
            print(f"更新主图片路径失败: {e}")

    async def _update_image_storage_paths(
        self, product_id: str, results: Dict[str, Any]
    ):
        """批量更新图片存储路径到数据库"""
        try:
            # 更新画廊图片路径
            for gallery_img in results["gallery_images"]:
                if gallery_img["success"]:
                    self.db_service.client.table("amazon_product_images").update(
                        {"storage_path": gallery_img["storage_path"]}
                    ).eq("product_id", product_id).eq("role", gallery_img["role"]).eq(
                        "position", gallery_img["position"]
                    ).execute()

            # 更新A+内容图片路径
            for aplus_img in results["aplus_images"]:
                if aplus_img["success"]:
                    self.db_service.client.table("amazon_aplus_images").update(
                        {"storage_path": aplus_img["storage_path"]}
                    ).eq("product_id", product_id).eq(
                        "position", aplus_img["position"]
                    ).execute()

        except Exception as e:
            print(f"批量更新图片路径失败: {e}")

    def _calculate_etag_short(self, scraped_data) -> str:
        """计算ETag的短版本（前8位）用于文件名"""
        from ..modules.store import DatabaseService

        db_service = DatabaseService()
        full_etag = db_service._calculate_etag(scraped_data)
        return full_etag[:8]  # 取前8位，如 2d4c399f

    async def _upload_with_cleanup(
        self,
        storage_path: str,
        image_data: bytes,
        asin: str,
        marketplace: str,
        role: str,
        position: int,
    ) -> bool:
        """上传文件前先清理同类型的旧文件"""
        try:
            from supabase import create_client

            supabase = create_client(
                settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
            )

            # 构建目录路径和文件模式
            if role == "aplus":
                dir_path = f"{marketplace}/{asin}/aplus"
                file_pattern = f"aplus_{position}_"
            elif role == "hero":
                # Hero图片模式: hero_*.jpg (不包含position)
                dir_path = f"{marketplace}/{asin}"
                file_pattern = f"{role}_"
            else:
                # Gallery等其他图片模式: gallery_{position}_*.jpg
                dir_path = f"{marketplace}/{asin}"
                file_pattern = f"{role}_{position}_"

            # 列出目录中的文件
            try:
                list_response = supabase.storage.from_(settings.STORAGE_BUCKET).list(
                    path=dir_path
                )

                if isinstance(list_response, list):
                    # 查找并删除同类型的旧文件
                    for file_info in list_response:
                        if file_info["name"].startswith(file_pattern):
                            old_file_path = f"{dir_path}/{file_info['name']}"
                            if old_file_path != storage_path:  # 不删除当前要上传的文件
                                try:
                                    supabase.storage.from_(
                                        settings.STORAGE_BUCKET
                                    ).remove([old_file_path])
                                    print(f"删除旧文件: {old_file_path}")
                                except Exception as delete_error:
                                    print(f"删除旧文件失败: {delete_error}")

            except Exception as list_error:
                print(f"列出文件失败，继续上传: {list_error}")

            # 上传新文件
            return await self._upload_to_supabase_storage(storage_path, image_data)

        except Exception as e:
            print(f"清理和上传失败: {e}")
            return False
