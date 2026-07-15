from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

LOCAL_DATABASE_URL = "postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_local"
TEMPORARY_IDENTITY_ENVIRONMENTS = frozenset({"local", "test", "ci"})


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
    database_echo: bool = False

    @model_validator(mode="after")
    def validate_database_configuration(self) -> "ApiSettings":
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
