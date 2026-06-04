from functools import lru_cache
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Seller WB AI Backend"
    app_env: str = "local"
    app_secret_key: str = Field(default="change-me", min_length=8)
    jwt_expire_minutes: int = 120
    jwt_bind_user_agent: bool = True
    database_url: str = "postgresql+psycopg://postgres:12345678@127.0.0.1:5432/seo_wb_db"
    db_auto_create: bool = False
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    openai_api_key: str | None = None
    openai_card_model: str | None = None
    openai_image_model: str = "gpt-image-2"
    fal_key: str | None = None
    fal_gpt_image_model: str = "gpt-image-2"
    redis_url: str | None = None
    redis_host: str | None = None
    redis_user: str | None = None
    redis_password: str | None = None
    redis_ssl: bool = False
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_host: str | None = None
    rabbitmq_port: int = 5672
    rabbitmq_username: str | None = None
    rabbitmq_password: str | None = None
    rabbitmq_vhost: str | None = None
    rabbitmq_ssl: bool = False

    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloud_dinary_name: str | None = None
    cloud_dinary_api_key: str | None = None
    cloud_dinary_api_secret: str | None = None
    generated_image_jpeg_quality: int = 88

    encryption_key: str | None = None
    wb_content_base_url: str = "https://content-api.wildberries.ru"
    wb_finance_api_base_url: str = "https://finance-api.wildberries.ru"
    wb_common_api_base_url: str = "https://common-api.wildberries.ru"
    enable_wb_raw_proxy: bool = False
    wb_live_tests: bool = False
    wb_live_full_product_sync: bool = False

    auth_cookie_name: str = "seller_wb_access"
    csrf_cookie_name: str = "seller_wb_csrf"
    admin_auth_cookie_name: str = "seller_wb_admin_access"
    admin_csrf_cookie_name: str = "seller_wb_admin_csrf"
    cookie_domain: str | None = None
    cookie_secure: bool | None = None
    cookie_samesite: str = "lax"

    auth_rate_limit_requests: int = 8
    auth_rate_limit_window_seconds: int = 300
    global_rate_limit_requests: int = 240
    global_rate_limit_window_seconds: int = 60

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800

    max_generate_images: int = 8
    max_ai_product_images: int = 10
    max_upload_image_bytes: int = 10 * 1024 * 1024
    max_job_files: int = 30
    max_media_upload_bytes: int = 15 * 1024 * 1024
    max_card_payload_bytes: int = 2 * 1024 * 1024

    max_ai_concurrency: int = 2
    max_background_jobs: int = 2
    openai_image_concurrency: int = 2
    openai_image_retry_attempts: int = 3
    enable_image_validation_retry: bool = False
    image_generation_lock_ttl_seconds: int = 1800

    wb_timeout_seconds: float = 30.0
    wb_media_timeout_seconds: float = 120.0
    wb_max_connections: int = 50
    wb_max_keepalive_connections: int = 20
    wb_retry_attempts: int = 3
    wb_retry_backoff_seconds: float = 0.5
    wb_catalog_cache_ttl_seconds: int = 900
    wb_finance_report_limit: int = 100000
    finance_auto_sync_timezone: str = "Europe/Moscow"
    finance_bootstrap_lookback_days: int = 7
    finance_scheduler_poll_seconds: int = 60
    finance_scheduler_leader_lock_seconds: int = 90
    finance_auto_job_lock_seconds: int = 1800
    usage_reset_scheduler_poll_seconds: int = 86400

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def should_secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env.lower() not in {"local", "development", "dev", "test"}

    @property
    def effective_redis_url(self) -> str | None:
        if self.redis_url:
            return self.redis_url
        if not self.redis_host:
            return None
        scheme = "rediss" if self.redis_ssl else "redis"
        auth = ""
        if self.redis_password:
            user = quote(self.redis_user or "default", safe="")
            password = quote(self.redis_password, safe="")
            auth = f"{user}:{password}@"
        return f"{scheme}://{auth}{self.redis_host}"

    @property
    def effective_rabbitmq_url(self) -> str:
        if not self.rabbitmq_host:
            return self.rabbitmq_url
        scheme = "amqps" if self.rabbitmq_ssl else "amqp"
        auth = ""
        if self.rabbitmq_username and self.rabbitmq_password:
            user = quote(self.rabbitmq_username, safe="")
            password = quote(self.rabbitmq_password, safe="")
            auth = f"{user}:{password}@"
        vhost = self.rabbitmq_vhost or ""
        if vhost.startswith("/"):
            vhost = vhost[1:]
        return f"{scheme}://{auth}{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"

    @property
    def effective_cloudinary_cloud_name(self) -> str | None:
        return self.cloudinary_cloud_name or self.cloud_dinary_name

    @property
    def effective_cloudinary_api_key(self) -> str | None:
        return self.cloudinary_api_key or self.cloud_dinary_api_key

    @property
    def effective_cloudinary_api_secret(self) -> str | None:
        return self.cloudinary_api_secret or self.cloud_dinary_api_secret

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.effective_cloudinary_cloud_name
            and self.effective_cloudinary_api_key
            and self.effective_cloudinary_api_secret
        )

    def validate_runtime_security(self) -> None:
        if self.app_env.lower() in {"local", "development", "dev", "test"}:
            return
        if self.app_secret_key == "change-me":
            raise RuntimeError("APP_SECRET_KEY must be changed outside local/test environments.")
        if not self.cors_origins:
            raise RuntimeError("CORS_ALLOW_ORIGINS must be configured outside local/test environments.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
