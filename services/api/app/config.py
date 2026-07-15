from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_environment: str = Field(default="local", min_length=1)
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_allowed_cors_origins: str = "http://localhost:3000"
    api_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

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


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    return ApiSettings()
