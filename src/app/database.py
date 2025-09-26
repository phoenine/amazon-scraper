"""
数据库连接和SQLAlchemy模型定义
"""

import os
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    Boolean,
    JSON,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import uuid

from .config import settings


# 数据库配置 - 使用config.py中的方法
DATABASE_URL = settings.get_database_url()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# 便利函数，直接使用settings中的方法
def get_database_url():
    """获取数据库连接URL - 委托给settings"""
    return settings.get_database_url()


class AmazonProduct(Base):
    __tablename__ = "amazon_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asin = Column(String, nullable=False)
    marketplace = Column(String, nullable=False)
    title = Column(Text)
    rating = Column(Float)
    ratings_count = Column(Integer)
    price_amount = Column(Float)
    price_currency = Column(String(3))
    hero_image_url = Column(Text)
    hero_image_path = Column(Text)
    availability = Column(Text)
    best_sellers_rank = Column(JSON)
    raw_html_snapshot_id = Column(
        UUID(as_uuid=True), ForeignKey("amazon_html_snapshots.id")
    )
    status = Column(String, nullable=False, default="pending")
    etag = Column(String)
    last_scraped_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    bullets = relationship(
        "AmazonProductBullet", back_populates="product", cascade="all, delete-orphan"
    )
    images = relationship(
        "AmazonProductImage", back_populates="product", cascade="all, delete-orphan"
    )
    attributes = relationship(
        "AmazonProductAttribute", back_populates="product", cascade="all, delete-orphan"
    )
    aplus_content = relationship(
        "AmazonAplusContent",
        back_populates="product",
        cascade="all, delete-orphan",
        uselist=False,
    )
    aplus_images = relationship(
        "AmazonAplusImage", back_populates="product", cascade="all, delete-orphan"
    )
    html_snapshot = relationship("AmazonHtmlSnapshot", back_populates="products")

    # 约束
    __table_args__ = (
        UniqueConstraint("asin", "marketplace", name="uq_asin_marketplace"),
    )


class AmazonProductBullet(Base):
    __tablename__ = "amazon_product_bullets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("amazon_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    position = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    product = relationship("AmazonProduct", back_populates="bullets")


class AmazonProductImage(Base):
    __tablename__ = "amazon_product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("amazon_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String, nullable=False)  # 'hero' or 'gallery'
    original_url = Column(Text, nullable=False)
    storage_path = Column(Text)
    width = Column(Integer)
    height = Column(Integer)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    product = relationship("AmazonProduct", back_populates="images")


class AmazonProductAttribute(Base):
    __tablename__ = "amazon_product_attributes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("amazon_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    source = Column(String, nullable=False)  # 'tech_details' or 'product_information'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    product = relationship("AmazonProduct", back_populates="attributes")


class AmazonAplusContent(Base):
    __tablename__ = "amazon_aplus_contents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("amazon_products.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # A+ content fields
    brand_story = Column(Text)
    faq = Column(JSON)  # JSON array of question-answer pairs
    product_information = Column(JSON)  # JSON object of key-value pairs

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    product = relationship("AmazonProduct", back_populates="aplus_content")


class AmazonAplusImage(Base):
    __tablename__ = "amazon_aplus_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("amazon_products.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Image basic info (following amazon_product_images pattern)
    original_url = Column(Text, nullable=False)
    storage_path = Column(Text)
    width = Column(Integer)
    height = Column(Integer)
    position = Column(Integer, nullable=False)

    # A+ specific fields
    alt_text = Column(Text)
    image_type = Column(String)
    content_section = Column(Text)  # brand_story, faq, product_info, etc.

    # Status management (simplified)
    status = Column(String, nullable=False, default="pending")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    product = relationship("AmazonProduct", back_populates="aplus_images")

    # 约束
    __table_args__ = (
        CheckConstraint(
            "image_type IN ('detail', 'scene', 'lifestyle', 'comparison', 'infographic')",
            name="ck_aplus_image_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'stored', 'failed')", name="ck_aplus_image_status"
        ),
    )


class AmazonHtmlSnapshot(Base):
    __tablename__ = "amazon_html_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asin = Column(String, nullable=False)
    marketplace = Column(String, nullable=False)
    html = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    products = relationship("AmazonProduct", back_populates="html_snapshot")


class ScrapeTask(Base):
    __tablename__ = "scrape_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asin = Column(String, nullable=False)
    marketplace = Column(String, nullable=False)
    status = Column(
        String, nullable=False, default="queued"
    )  # 'queued', 'running', 'success', 'failed'
    error = Column(Text)
    requested_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
