from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MarketplaceEnum(str, Enum):
    US = "amazon.com"
    JP = "amazon.co.jp"
    DE = "amazon.de"
    UK = "amazon.co.uk"
    FR = "amazon.fr"

class StatusEnum(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    FAILED = "failed"
    PENDING = "pending"

class TaskStatusEnum(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class ImageRoleEnum(str, Enum):
    HERO = "hero"
    GALLERY = "gallery"

class AttributeSourceEnum(str, Enum):
    TECH_DETAILS = "tech_details"
    PRODUCT_INFORMATION = "product_information"

# A+ Content Enums
class AplusImageTypeEnum(str, Enum):
    DETAIL = "detail"
    SCENE = "scene"
    LIFESTYLE = "lifestyle"
    COMPARISON = "comparison"
    INFOGRAPHIC = "infographic"

class AplusImageStatusEnum(str, Enum):
    PENDING = "pending"
    STORED = "stored"
    FAILED = "failed"

# Request Models
class ScrapeItem(BaseModel):
    asin: str = Field(..., description="Amazon Standard Identification Number")
    marketplace: Optional[str] = Field(default="amazon.com", description="Amazon marketplace")

class ScrapeRequest(BaseModel):
    items: List[ScrapeItem] = Field(..., description="List of products to scrape")
    async_mode: Optional[bool] = Field(default=True, description="Return immediately with task IDs")

# Response Models
class PriceInfo(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None

class ImageInfo(BaseModel):
    url: Optional[str] = None
    storage_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    position: Optional[int] = None

class ProductAttribute(BaseModel):
    name: str
    value: str
    source: AttributeSourceEnum

# A+ Content Models
class AplusContent(BaseModel):
    brand_story: Optional[str] = None
    faq: Optional[List[Dict[str, str]]] = None  # List of question-answer pairs
    product_information: Optional[Dict[str, Any]] = None  # Key-value pairs

class AplusImage(BaseModel):
    original_url: str
    storage_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    position: int
    alt_text: Optional[str] = None
    image_type: Optional[AplusImageTypeEnum] = None
    content_section: Optional[str] = None  # brand_story, faq, product_info, etc.
    status: AplusImageStatusEnum = AplusImageStatusEnum.PENDING

class ProductResponse(BaseModel):
    id: str
    asin: str
    marketplace: str
    title: Optional[str] = None
    rating: Optional[float] = None
    ratings_count: Optional[int] = None
    price: Optional[PriceInfo] = None
    hero_image: Optional[ImageInfo] = None
    gallery: List[ImageInfo] = []
    bullets: List[str] = []
    attributes: List[ProductAttribute] = []
    availability: Optional[str] = None
    best_sellers_rank: Optional[Dict[str, Any]] = None
    aplus_content: Optional[AplusContent] = None
    aplus_images: List[AplusImage] = []
    status: StatusEnum
    etag: Optional[str] = None
    last_scraped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class TaskResponse(BaseModel):
    id: str
    asin: str
    marketplace: str
    status: TaskStatusEnum
    error: Optional[str] = None
    requested_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Internal Models
class ScrapedProduct(BaseModel):
    asin: str
    marketplace: str
    title: Optional[str] = None
    rating: Optional[float] = None
    ratings_count: Optional[int] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    hero_image_url: Optional[str] = None
    availability: Optional[str] = None
    best_sellers_rank: Optional[Dict[str, Any]] = None
    bullets: List[str] = []
    gallery_images: List[Dict[str, Any]] = []
    attributes: List[ProductAttribute] = []
    aplus_content: Optional[AplusContent] = None
    aplus_images: List[AplusImage] = []
    raw_html: Optional[str] = None