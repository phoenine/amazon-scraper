import uuid
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from supabase import create_client, Client

from ..config import settings
from .models import (
    ProductResponse,
    TaskResponse,
    ScrapedProduct,
    TaskStatusEnum,
    StatusEnum,
    AplusContent,
    AplusImage,
    AplusImageStatusEnum,
)


class DatabaseService:
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )

    async def get_product(
        self, asin: str, marketplace: str
    ) -> Optional[ProductResponse]:
        """Get product from database with all related data"""
        try:
            # Get main product
            result = (
                self.client.table("amazon_products")
                .select("*")
                .eq("asin", asin)
                .eq("marketplace", marketplace)
                .execute()
            )

            if not result.data:
                return None

            product = result.data[0]
            product_id = product["id"]

            # Get bullets
            bullets_result = (
                self.client.table("amazon_product_bullets")
                .select("text")
                .eq("product_id", product_id)
                .order("position")
                .execute()
            )
            bullets = [item["text"] for item in bullets_result.data]

            # Get images
            images_result = (
                self.client.table("amazon_product_images")
                .select("*")
                .eq("product_id", product_id)
                .order("position")
                .execute()
            )

            hero_image = None
            gallery = []

            for img in images_result.data:
                img_info = {
                    "url": img["original_url"],
                    "storage_path": img["storage_path"],
                    "position": img["position"],
                }

                if img["role"] == "hero":
                    hero_image = img_info
                else:
                    gallery.append(img_info)

            # Get A+ content
            aplus_content = None
            aplus_content_result = (
                self.client.table("amazon_aplus_contents")
                .select("*")
                .eq("product_id", product_id)
                .execute()
            )

            if aplus_content_result.data:
                aplus_data = aplus_content_result.data[0]
                aplus_content = AplusContent(
                    brand_story=aplus_data["brand_story"],
                    faq=json.loads(aplus_data["faq"]) if aplus_data["faq"] else None,
                    product_information=(
                        json.loads(aplus_data["product_information"])
                        if aplus_data["product_information"]
                        else None
                    ),
                )

            # Get A+ images
            aplus_images = []
            aplus_images_result = (
                self.client.table("amazon_aplus_images")
                .select("*")
                .eq("product_id", product_id)
                .order("position")
                .execute()
            )

            for img in aplus_images_result.data:
                aplus_images.append(
                    AplusImage(
                        original_url=img["original_url"],
                        storage_path=img["storage_path"],
                        role=img["role"],
                        position=img["position"],
                        status=img["status"],
                    )
                )

            return ProductResponse(
                id=product["id"],
                asin=product["asin"],
                marketplace=product["marketplace"],
                title=product["title"],
                rating=float(product["rating"]) if product["rating"] else None,
                ratings_count=product["ratings_count"],
                price=(
                    {
                        "amount": (
                            float(product["price_amount"])
                            if product["price_amount"]
                            else None
                        ),
                        "currency": product["price_currency"],
                    }
                    if product["price_amount"] or product["price_currency"]
                    else None
                ),
                hero_image=hero_image,
                gallery=gallery,
                bullets=bullets,
                best_sellers_rank=product["best_sellers_rank"],
                aplus_content=aplus_content,
                aplus_images=aplus_images,
                status=product["status"],
                etag=product["etag"],
                last_scraped_at=product["last_scraped_at"],
                created_at=product["created_at"],
                updated_at=product["updated_at"],
            )

        except Exception as e:
            print(f"Error getting product: {e}")
            return None

    async def upsert_product(self, scraped_data: ScrapedProduct) -> Tuple[str, bool]:
        """Insert or update product data, returns (product_id, content_changed)"""
        try:
            etag = self._calculate_etag(scraped_data)

            product_data = {
                "asin": scraped_data.asin,
                "marketplace": scraped_data.marketplace,
                "title": scraped_data.title,
                "rating": scraped_data.rating,
                "ratings_count": scraped_data.ratings_count,
                "price_amount": scraped_data.price_amount,
                "price_currency": scraped_data.price_currency,
                "best_sellers_rank": scraped_data.best_sellers_rank,
                "status": "fresh",
                "etag": etag,
                "last_scraped_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            # Check if product exists
            existing = (
                self.client.table("amazon_products")
                .select("id, etag")
                .eq("asin", scraped_data.asin)
                .eq("marketplace", scraped_data.marketplace)
                .execute()
            )

            content_changed = True  # 默认认为内容有变化

            if existing.data:
                product_id = existing.data[0]["id"]

                # 情况3：ETag变化了，需要更新所有信息包括A+
                if existing.data[0]["etag"] != etag:
                    self.client.table("amazon_products").update(product_data).eq(
                        "id", product_id
                    ).execute()

                    # 删除并重建所有相关数据，包括A+内容
                    await self._update_related_data(
                        product_id, scraped_data, include_aplus=True
                    )
                    content_changed = True
                else:
                    # 情况1：ETag没有变化，只更新时间戳和可变字段，不更新A+
                    variable_fields_data = {
                        "rating": scraped_data.rating,
                        "ratings_count": scraped_data.ratings_count,
                        "price_amount": scraped_data.price_amount,
                        "price_currency": scraped_data.price_currency,
                        "best_sellers_rank": scraped_data.best_sellers_rank,
                        "last_scraped_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                    self.client.table("amazon_products").update(
                        variable_fields_data
                    ).eq("id", product_id).execute()
                    content_changed = False  # 核心内容没有变化
            else:
                # 情况2：新数据，需要更新所有信息包括A+
                product_data["id"] = str(uuid.uuid4())
                product_data["created_at"] = datetime.utcnow().isoformat()

                result = (
                    self.client.table("amazon_products").insert(product_data).execute()
                )
                product_id = result.data[0]["id"]

                # 插入所有相关数据，包括A+内容
                await self._insert_related_data(
                    product_id, scraped_data, include_aplus=True
                )
                content_changed = True

            return product_id, content_changed

        except Exception as e:
            print(f"Error upserting product: {e}")
            raise

    async def _insert_related_data(
        self, product_id: str, scraped_data: ScrapedProduct, include_aplus: bool = True
    ):
        """Insert bullets, images, and optionally A+ content"""
        # Insert bullets
        if scraped_data.bullets:
            bullets_data = [
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "position": i + 1,
                    "text": bullet,
                }
                for i, bullet in enumerate(scraped_data.bullets)
            ]
            self.client.table("amazon_product_bullets").insert(bullets_data).execute()

        # Insert images
        images_data = []

        # Hero image - 现在存储在 amazon_product_images 表中
        if scraped_data.hero_image_url:
            images_data.append(
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "role": "hero",
                    "original_url": scraped_data.hero_image_url,
                    "storage_path": None,  # 添加 storage_path 字段
                    "position": 0,
                }
            )

        for i, img in enumerate(scraped_data.gallery_images):
            images_data.append(
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "role": "gallery",
                    "original_url": img.get("url"),
                    "storage_path": img.get("storage_path"),
                    "position": i,
                }
            )

        if images_data:
            self.client.table("amazon_product_images").insert(images_data).execute()

        # Insert A+ content only if include_aplus is True
        if include_aplus:
            await self._insert_aplus_data(product_id, scraped_data)

    async def _insert_aplus_data(self, product_id: str, scraped_data: ScrapedProduct):
        """Insert A+ content and images"""
        # Insert A+ content
        if scraped_data.aplus_content:
            aplus_data = {
                "id": str(uuid.uuid4()),
                "product_id": product_id,
                "brand_story": scraped_data.aplus_content.brand_story,
                "faq": (
                    json.dumps(scraped_data.aplus_content.faq)
                    if scraped_data.aplus_content.faq
                    else None
                ),
                "product_information": (
                    json.dumps(scraped_data.aplus_content.product_information)
                    if scraped_data.aplus_content.product_information
                    else None
                ),
            }
            self.client.table("amazon_aplus_contents").insert(aplus_data).execute()

        # Insert A+ images
        if scraped_data.aplus_images:
            aplus_images_data = [
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "original_url": img.original_url,
                    "storage_path": img.storage_path,
                    "role": img.role,
                    "position": img.position,
                    "status": img.status,
                }
                for img in scraped_data.aplus_images
            ]
            self.client.table("amazon_aplus_images").insert(aplus_images_data).execute()

    async def _update_related_data(
        self, product_id: str, scraped_data: ScrapedProduct, include_aplus: bool = True
    ):
        """Update related data by deleting and reinserting"""
        # Delete existing core data (always updated)
        self.client.table("amazon_product_bullets").delete().eq(
            "product_id", product_id
        ).execute()
        self.client.table("amazon_product_images").delete().eq(
            "product_id", product_id
        ).execute()

        # Delete A+ data only if include_aplus is True
        if include_aplus:
            self.client.table("amazon_aplus_contents").delete().eq(
                "product_id", product_id
            ).execute()
            self.client.table("amazon_aplus_images").delete().eq(
                "product_id", product_id
            ).execute()

        # Insert new data
        await self._insert_related_data(product_id, scraped_data, include_aplus)

    def _calculate_etag(self, scraped_data: ScrapedProduct) -> str:
        """Calculate content hash for change detection"""
        content = {
            "title": scraped_data.title,
            # "rating": scraped_data.rating,
            # "price_amount": scraped_data.price_amount,
            "bullets": scraped_data.bullets,
            "hero_image_url": scraped_data.hero_image_url,
            "gallery_images": scraped_data.gallery_images,
        }

        content_str = json.dumps(content, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()

    async def create_task(
        self, asin: str, marketplace: str, requested_by: Optional[str] = None
    ) -> str:
        """Create a new scraping task"""
        task_data = {
            "id": str(uuid.uuid4()),
            "asin": asin,
            "marketplace": marketplace,
            "status": TaskStatusEnum.QUEUED,
            "requested_by": requested_by,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = self.client.table("scrape_tasks").insert(task_data).execute()
        return result.data[0]["id"]

    async def update_task_status(
        self, task_id: str, status: TaskStatusEnum, error: Optional[str] = None
    ):
        """Update task status"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if error:
            update_data["error"] = error

        self.client.table("scrape_tasks").update(update_data).eq(
            "id", task_id
        ).execute()

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Get task by ID"""
        result = (
            self.client.table("scrape_tasks").select("*").eq("id", task_id).execute()
        )

        if not result.data:
            return None

        task = result.data[0]
        return TaskResponse(
            id=task["id"],
            asin=task["asin"],
            marketplace=task["marketplace"],
            status=task["status"],
            error=task["error"],
            requested_by=task["requested_by"],
            created_at=task["created_at"],
            updated_at=task["updated_at"],
        )

    async def is_product_fresh(self, asin: str, marketplace: str) -> bool:
        """Check if product data is fresh (within TTL)"""
        result = (
            self.client.table("amazon_products")
            .select("last_scraped_at")
            .eq("asin", asin)
            .eq("marketplace", marketplace)
            .execute()
        )

        if not result.data:
            return False

        last_scraped = datetime.fromisoformat(
            result.data[0]["last_scraped_at"].replace("Z", "+00:00")
        )

        ttl_threshold = datetime.now(timezone.utc) - timedelta(
            seconds=settings.SCRAPER_TTL_SECONDS
        )

        return last_scraped > ttl_threshold

    async def get_stats(self) -> Dict[str, Any]:
        """Get scraping statistics"""
        # Product counts by status
        products_result = (
            self.client.table("amazon_products")
            .select("status", count="exact")
            .execute()
        )

        # Task counts by status
        tasks_result = (
            self.client.table("scrape_tasks").select("status", count="exact").execute()
        )

        return {
            "total_products": products_result.count,
            "total_tasks": tasks_result.count,
            "last_updated": datetime.utcnow().isoformat(),
        }
