"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Настройки приложения"""

    # API Gateway
    api_gateway_host: str = "0.0.0.0"
    api_gateway_port: int = 8000
    api_gateway_reload: bool = True

    # Database
    postgres_host: str = "localhost"  # В Docker будет переопределено через DATABASE_URL или POSTGRES_HOST
    postgres_port: int = 5432
    postgres_db: str = "testops_copilot"
    postgres_user: str = "testops"
    postgres_password: str = "testops_password"

    @property
    def database_url(self) -> str:
        # Проверяем переменную окружения DATABASE_URL (для Docker)
        if os.getenv("DATABASE_URL"):
            return os.getenv("DATABASE_URL")
        # Или используем POSTGRES_HOST если задан
        host = os.getenv("POSTGRES_HOST", self.postgres_host)
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{host}:{self.postgres_port}/{self.postgres_db}"

    # Redis
    redis_host: str = "localhost"  # В Docker будет переопределено через REDIS_URL или REDIS_HOST
    redis_port: int = 6379
    redis_db_queue: int = 0
    redis_db_result: int = 1
    redis_db_cache: int = 2
    redis_db_pubsub: int = 3

    @property
    def redis_url(self) -> str:
        if os.getenv("REDIS_URL"):
            return os.getenv("REDIS_URL")
        host = os.getenv("REDIS_HOST", self.redis_host)
        return f"redis://{host}:{self.redis_port}/{self.redis_db_queue}"

    @property
    def redis_result_url(self) -> str:
        if os.getenv("REDIS_URL"):
            base = os.getenv("REDIS_URL").rsplit("/", 1)[0]
            return f"{base}/{self.redis_db_result}"
        host = os.getenv("REDIS_HOST", self.redis_host)
        return f"redis://{host}:{self.redis_port}/{self.redis_db_result}"

    @property
    def redis_cache_url(self) -> str:
        if os.getenv("REDIS_URL"):
            base = os.getenv("REDIS_URL").rsplit("/", 1)[0]
            return f"{base}/{self.redis_db_cache}"
        host = os.getenv("REDIS_HOST", self.redis_host)
        return f"redis://{host}:{self.redis_port}/{self.redis_db_cache}"

    @property
    def redis_pubsub_url(self) -> str:
        if os.getenv("REDIS_URL"):
            base = os.getenv("REDIS_URL").rsplit("/", 1)[0]
            return f"{base}/{self.redis_db_pubsub}"
        host = os.getenv("REDIS_HOST", self.redis_host)
        return f"redis://{host}:{self.redis_port}/{self.redis_db_pubsub}"

    # Cloud.ru IAM API
    cloud_ru_iam_url: str = "https://iam.api.cloud.ru/api/v1/auth/token"
    cloud_ru_key_id: str = "ed9fb8b4b60c2dbc8a68b5c948b6bb0b"
    cloud_ru_key_secret: str = "dda8755d7065d1afe4519038721d630d"

    # Cloud.ru Foundation Models API
    cloud_ru_foundation_models_url: str = "https://foundation-models.api.cloud.ru/v1"
    cloud_ru_api_key: str = "OTk0NDYzYWItMjc5MC00ZDVkLWE0ZTYtNWRjMDMyZGZmYmVi.7a3af6364ac5ed623f1186d783168b8e"
    cloud_ru_default_model: str = "ai-sage/GigaChat3-10B-A1.8B"  # Модель по умолчанию

    # Evolution Compute API
    evolution_compute_api_url: str = "https://compute.api.cloud.ru"
    evolution_compute_project_id: str = "4464d629-b915-4989-b652-aaff809f9423"
    evolution_compute_token: Optional[str] = None

    # GitLab (опционально)
    gitlab_url: Optional[str] = None
    gitlab_token: Optional[str] = None
    gitlab_project_id: Optional[str] = None

    # GitHub (опционально, альтернатива GitLab)
    github_token: Optional[str] = None
    github_repo_name: Optional[str] = None  # формат: "username/repo-name"

    # Jira (опционально, для интеграции с дефектами)
    jira_url: Optional[str] = None
    jira_token: Optional[str] = None
    jira_email: Optional[str] = None  # Для Jira Cloud Basic Auth

    # Allure TestOps (опционально, для интеграции с дефектами)
    allure_testops_url: Optional[str] = None
    allure_testops_token: Optional[str] = None

    # JWT (опционально для MVP)
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 10

    # Celery
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    @property
    def celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def celery_result(self) -> str:
        return self.celery_result_backend or self.redis_result_url

    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: list = ["json"]
    celery_timezone: str = "UTC"
    celery_task_timeout: int = 3600

    # LangGraph
    langgraph_checkpoint_db: Optional[str] = None

    @property
    def langgraph_checkpoint(self) -> str:
        return self.langgraph_checkpoint_db or self.database_url

    # Safety Guard
    safety_guard_enabled: bool = True
    safety_guard_sandbox_enabled: bool = False

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Дополнительные переменные из .env (для совместимости)
    evolution_key_id: Optional[str] = None
    evolution_key_secret: Optional[str] = None
    evolution_llm_api_key: Optional[str] = None
    evolution_llm_api_url: Optional[str] = None
    project_id: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Игнорировать лишние переменные из .env


# Глобальный экземпляр настроек
settings = Settings()
