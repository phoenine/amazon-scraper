import uuid
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from supabase import create_client, Client

from ..config import settings
from .models import (
    ProductResponse,
    TaskResponse,
    ScrapedProduct,
    TaskStatusEnum,
    StatusEnum,
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
                    "width": img["width"],
                    "height": img["height"],
                    "position": img["position"],
                }

                if img["role"] == "hero":
                    hero_image = img_info
                else:
                    gallery.append(img_info)

            # Get attributes
            attrs_result = (
                self.client.table("amazon_product_attributes")
                .select("*")
                .eq("product_id", product_id)
                .execute()
            )
            attributes = [
                {"name": attr["name"], "value": attr["value"], "source": attr["source"]}
                for attr in attrs_result.data
            ]

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
                attributes=attributes,
                availability=product["availability"],
                best_sellers_rank=product["best_sellers_rank"],
                status=product["status"],
                etag=product["etag"],
                last_scraped_at=product["last_scraped_at"],
                created_at=product["created_at"],
                updated_at=product["updated_at"],
            )

        except Exception as e:
            print(f"Error getting product: {e}")
            return None

    async def upsert_product(self, scraped_data: ScrapedProduct) -> str:
        """Insert or update product with all related data"""
        try:
            # Calculate etag
            etag = self._calculate_etag(scraped_data)

            # Check if product exists
            existing = (
                self.client.table("amazon_products")
                .select("id, etag")
                .eq("asin", scraped_data.asin)
                .eq("marketplace", scraped_data.marketplace)
                .execute()
            )

            product_data = {
                "asin": scraped_data.asin,
                "marketplace": scraped_data.marketplace,
                "title": scraped_data.title,
                "rating": scraped_data.rating,
                "ratings_count": scraped_data.ratings_count,
                "price_amount": scraped_data.price_amount,
                "price_currency": scraped_data.price_currency,
                "hero_image_url": scraped_data.hero_image_url,
                "availability": scraped_data.availability,
                "best_sellers_rank": scraped_data.best_sellers_rank,
                "status": StatusEnum.FRESH,
                "etag": etag,
                "last_scraped_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            if existing.data:
                # Update existing product
                product_id = existing.data[0]["id"]

                # Only update if etag changed
                if existing.data[0]["etag"] != etag:
                    self.client.table("amazon_products").update(product_data).eq(
                        "id", product_id
                    ).execute()

                    # Delete and recreate related data
                    await self._update_related_data(product_id, scraped_data)
                else:
                    # Just update last_scraped_at
                    self.client.table("amazon_products").update(
                        {
                            "last_scraped_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    ).eq("id", product_id).execute()
            else:
                # Insert new product
                product_data["id"] = str(uuid.uuid4())
                product_data["created_at"] = datetime.utcnow().isoformat()

                result = (
                    self.client.table("amazon_products").insert(product_data).execute()
                )
                product_id = result.data[0]["id"]

                # Insert related data
                await self._insert_related_data(product_id, scraped_data)

            return product_id

        except Exception as e:
            print(f"Error upserting product: {e}")
            raise

    async def _insert_related_data(self, product_id: str, scraped_data: ScrapedProduct):
        """Insert bullets, images, and attributes"""
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

        # Hero image
        if scraped_data.hero_image_url:
            images_data.append(
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "role": "hero",
                    "original_url": scraped_data.hero_image_url,
                    "position": 0,
                }
            )

        # Gallery images
        for i, img in enumerate(scraped_data.gallery_images):
            images_data.append(
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "role": "gallery",
                    "original_url": img.get("url"),
                    "width": img.get("width"),
                    "height": img.get("height"),
                    "position": i + 1,
                }
            )

        if images_data:
            self.client.table("amazon_product_images").insert(images_data).execute()

        # Insert attributes
        if scraped_data.attributes:
            attrs_data = [
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "name": attr.name,
                    "value": attr.value,
                    "source": attr.source,
                }
                for attr in scraped_data.attributes
            ]
            self.client.table("amazon_product_attributes").insert(attrs_data).execute()

    async def _update_related_data(self, product_id: str, scraped_data: ScrapedProduct):
        """Update related data by deleting and reinserting"""
        # Delete existing related data
        self.client.table("amazon_product_bullets").delete().eq(
            "product_id", product_id
        ).execute()
        self.client.table("amazon_product_images").delete().eq(
            "product_id", product_id
        ).execute()
        self.client.table("amazon_product_attributes").delete().eq(
            "product_id", product_id
        ).execute()

        # Insert new data
        await self._insert_related_data(product_id, scraped_data)

    def _calculate_etag(self, scraped_data: ScrapedProduct) -> str:
        """Calculate content hash for change detection"""
        content = {
            "title": scraped_data.title,
            "rating": scraped_data.rating,
            "price_amount": scraped_data.price_amount,
            "bullets": scraped_data.bullets,
            "attributes": [
                {"name": attr.name, "value": attr.value}
                for attr in scraped_data.attributes
            ],
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()

    async def create_task(
        self, asin: str, marketplace: str, requested_by: Optional[str] = None
    ) -> str:
        """Create a new scraping task"""
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "asin": asin,
            "marketplace": marketplace,
            "status": TaskStatusEnum.QUEUED,
            "requested_by": requested_by,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        self.client.table("scrape_tasks").insert(task_data).execute()
        return task_id

    async def update_task_status(
        self, task_id: str, status: TaskStatusEnum, error: Optional[str] = None
    ):
        """Update task status"""
        update_data = {"status": status, "updated_at": datetime.utcnow().isoformat()}

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
        return TaskResponse(**task)

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
