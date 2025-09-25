import os
from typing import Optional


class Settings:
    """应用配置类"""

    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Scraper Configuration
    SCRAPER_CONCURRENCY_PER_DOMAIN: int = int(
        os.getenv("SCRAPER_CONCURRENCY_PER_DOMAIN", "3")
    )
    SCRAPER_GLOBAL_CONCURRENCY: int = int(os.getenv("SCRAPER_GLOBAL_CONCURRENCY", "6"))
    SCRAPER_TTL_SECONDS: int = int(
        os.getenv("SCRAPER_TTL_SECONDS", "86400")
    )  # 24 hours

    # Browser Configuration
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "30000"))  # 30 seconds

    # Storage Configuration
    STORAGE_BUCKET: str = os.getenv("STORAGE_BUCKET", "amazon-assets")

    # Worker Configuration
    WORKER_COUNT: int = int(os.getenv("WORKER_COUNT", "3"))
    WORKER_RETRY_ATTEMPTS: int = int(os.getenv("WORKER_RETRY_ATTEMPTS", "3"))
    WORKER_RETRY_DELAY: int = int(os.getenv("WORKER_RETRY_DELAY", "5"))  # seconds

    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        # 1. 优先使用直接配置的DATABASE_URL
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # 2. 检查Supabase配置是否完整
        if not self.SUPABASE_URL:
            raise ValueError("缺少SUPABASE_URL环境变量")

        if not self.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("缺少SUPABASE_SERVICE_ROLE_KEY环境变量")

        # 3. 从Supabase URL构建PostgreSQL连接字符串
        supabase_url = self.SUPABASE_URL.strip()

        # 处理本地Supabase (http://localhost:8000)
        if supabase_url.startswith("http://localhost"):
            return "postgresql://postgres:postgres@localhost:54322/postgres"

        # 处理标准的Supabase URL格式 (https://)
        elif supabase_url.startswith("https://"):
            # 提取项目引用
            url_without_protocol = supabase_url.replace("https://", "")

            if ".supabase.co" in url_without_protocol:
                project_ref = url_without_protocol.replace(".supabase.co", "")
                return f"postgresql://postgres:{self.SUPABASE_SERVICE_ROLE_KEY}@db.{project_ref}.supabase.co:5432/postgres"
            else:
                raise ValueError(f"无效的Supabase URL格式: {supabase_url}")

        # 处理已经是PostgreSQL URL的情况
        elif supabase_url.startswith("postgresql://") or supabase_url.startswith(
            "postgres://"
        ):
            return supabase_url

        # 处理其他格式
        else:
            raise ValueError(
                f"不支持的URL格式: {supabase_url}。"
                "请使用标准的Supabase URL (https://xxx.supabase.co) "
                "或本地开发URL (http://localhost:8000) "
                "或PostgreSQL连接字符串 (postgresql://...)"
            )


settings = Settings()
