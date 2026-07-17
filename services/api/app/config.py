from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

LOCAL_DATABASE_URL = "postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_local"
TEMPORARY_IDENTITY_ENVIRONMENTS = frozenset({"local", "test", "ci"})
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_environment: str = Field(default="local", min_length=1)
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_allowed_cors_origins: str = "http://localhost:3000"
    api_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str | None = None
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=50)
    database_pool_timeout_seconds: float = Field(default=10, gt=0, le=120)
    database_statement_timeout_ms: int = Field(default=5000, ge=100, le=120_000)
    database_echo: bool = False
    api_max_request_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)
    api_max_upload_bytes: int = Field(default=104_857_600, ge=1, le=104_857_600)
    source_object_storage_adapter: Literal["local_filesystem_v1", "disabled"] = (
        "local_filesystem_v1"
    )
    source_object_storage_root: str = Field(default=".local/source-objects", min_length=1)
    model_provider: Literal["deterministic_offline", "deepseek"] = "deterministic_offline"
    deepseek_api_key: str | None = Field(default=None, repr=False)
    deepseek_base_url: str = DEEPSEEK_BASE_URL
    deepseek_model: str = DEEPSEEK_MODEL
    deepseek_timeout_seconds: float = Field(default=60, gt=0, le=60)
    deepseek_max_attempts: int = Field(default=2, ge=1, le=2)
    deepseek_max_input_bytes: int = Field(default=131_072, ge=1024, le=262_144)
    deepseek_max_output_bytes: int = Field(default=262_144, ge=1024, le=262_144)

    @model_validator(mode="after")
    def validate_database_configuration(self) -> "ApiSettings":
        if self.model_provider == "deepseek":
            if not self.deepseek_api_key:
                raise ValueError("DEEPSEEK_API_KEY is required when MODEL_PROVIDER=deepseek")
            parsed_provider = urlparse(self.deepseek_base_url)
            if (
                self.deepseek_base_url != DEEPSEEK_BASE_URL
                or parsed_provider.scheme != "https"
                or parsed_provider.netloc != "api.deepseek.com"
                or parsed_provider.path not in {"", "/"}
                or parsed_provider.params
                or parsed_provider.query
                or parsed_provider.fragment
                or parsed_provider.username
                or parsed_provider.password
            ):
                raise ValueError("DEEPSEEK_BASE_URL must be the approved HTTPS DeepSeek origin")
            if self.deepseek_model != DEEPSEEK_MODEL:
                raise ValueError("DEEPSEEK_MODEL must be deepseek-v4-flash")
        if (
            self.source_object_storage_adapter == "local_filesystem_v1"
            and self.app_environment not in TEMPORARY_IDENTITY_ENVIRONMENTS
        ):
            raise ValueError("local filesystem object storage is only allowed in local/test/ci")
        if self.database_url is None:
            if self.app_environment not in TEMPORARY_IDENTITY_ENVIRONMENTS:
                raise ValueError("DATABASE_URL is required outside local, test, and ci")
            return self

        url = make_url(self.database_url)
        if url.get_backend_name() != "postgresql" or url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if not url.database:
            raise ValueError("DATABASE_URL must name a database")
        if self.database_echo and self.app_environment not in {"local", "test"}:
            raise ValueError("DATABASE_ECHO is only allowed in local or test")
        return self

    @field_validator("api_allowed_cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("API_ALLOWED_CORS_ORIGINS must contain at least one origin")
        for origin in origins:
            parsed = urlparse(origin)
            if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("CORS origins must be explicit absolute http(s) origins")
            if parsed.username or parsed.password or parsed.path not in {"", "/"}:
                raise ValueError("CORS origins must not contain credentials or paths")
        return ",".join(origins)

    @property
    def allowed_cors_origins(self) -> list[str]:
        return self.api_allowed_cors_origins.split(",")

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or LOCAL_DATABASE_URL

    @property
    def redacted_database_url(self) -> str:
        return make_url(self.resolved_database_url).render_as_string(hide_password=True)

    @property
    def temporary_identity_headers_enabled(self) -> bool:
        return self.app_environment in TEMPORARY_IDENTITY_ENVIRONMENTS


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    return ApiSettings()
