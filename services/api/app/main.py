import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from services.api.app.config import ApiSettings, get_api_settings
from services.api.app.logging import configure_logging
from services.api.app.metadata import SERVICE_NAME, SERVICE_VERSION
from services.api.app.routes.health import router as health_router

logger = logging.getLogger(__name__)


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_api_settings()
    configure_logging(resolved_settings.app_environment, resolved_settings.api_log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("api startup", extra={"event": "api.startup"})
        yield
        logger.info("api shutdown", extra={"event": "api.shutdown"})

    app = FastAPI(
        title="Foundation Core API",
        version=SERVICE_VERSION,
        debug=False,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.include_router(health_router)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/api/v1/health", status_code=307)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "unhandled API error",
            extra={"event": "api.unhandled_error", "path": request.url.path},
            exc_info=error,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()

__all__ = ["app", "create_app", "SERVICE_NAME"]
