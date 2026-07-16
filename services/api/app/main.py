import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.document_extraction_services import (
    DocumentExtractionApplicationService,
)
from services.api.app.application.errors import (
    ApplicationError,
    ResourceConflict,
    ResourceNotFound,
    StorageUnavailable,
    TemporaryIdentityDisabled,
)
from services.api.app.application.ingestion_services import BriefIngestionApplicationService
from services.api.app.application.services import TenantApplicationService
from services.api.app.application.source_asset_services import SourceAssetApplicationService
from services.api.app.application.source_object_services import SourceObjectApplicationService
from services.api.app.application.storage import (
    DisabledStorageAdapter,
    LocalFilesystemStorageAdapter,
)
from services.api.app.config import ApiSettings, get_api_settings
from services.api.app.domain import (
    ApprovalBlocked,
    DomainError,
    InvalidBriefMutation,
    InvalidBriefTransition,
    InvalidProjectMutation,
    InvalidProjectTransition,
    InvalidSourceAssetMutation,
    VersionConflict,
)
from services.api.app.infrastructure.database import create_database_engine, create_session_factory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.app.logging import configure_logging
from services.api.app.metadata import SERVICE_NAME, SERVICE_VERSION
from services.api.app.presentation.brief_routes import router as brief_router
from services.api.app.presentation.document_extraction_routes import (
    router as document_extraction_router,
)
from services.api.app.presentation.ingestion_routes import router as ingestion_router
from services.api.app.presentation.routes import router as tenant_router
from services.api.app.presentation.source_asset_routes import router as source_asset_router
from services.api.app.presentation.source_object_routes import router as source_object_router
from services.api.app.routes.health import router as health_router

logger = logging.getLogger(__name__)
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
TEMPORARY_IDENTITY_HEADERS = (
    "x-actor-subject",
    "x-organization-id",
    "x-workspace-id",
)


def error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
            }
        },
        headers={"X-Correlation-Id": correlation_id},
    )


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_api_settings()
    configure_logging(resolved_settings.app_environment, resolved_settings.api_log_level)
    engine = create_database_engine(resolved_settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("api startup", extra={"event": "api.startup"})
        try:
            yield
        finally:
            engine.dispose()
            logger.info("api shutdown", extra={"event": "api.shutdown"})

    app = FastAPI(
        title="Foundation Core API",
        version=SERVICE_VERSION,
        debug=False,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.tenant_application_service = TenantApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory)
    )
    app.state.brief_application_service = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory)
    )
    app.state.ingestion_application_service = BriefIngestionApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory)
    )
    app.state.source_asset_application_service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory)
    )
    storage = (
        LocalFilesystemStorageAdapter(Path(resolved_settings.source_object_storage_root))
        if resolved_settings.source_object_storage_adapter == "local_filesystem_v1"
        else DisabledStorageAdapter()
    )
    app.state.source_object_application_service = SourceObjectApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory),
        storage,
        max_upload_bytes=resolved_settings.api_max_upload_bytes,
    )
    app.state.document_extraction_application_service = DocumentExtractionApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory), storage
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "X-Actor-Subject",
            "X-Organization-Id",
            "X-Workspace-Id",
            "X-Correlation-Id",
            "Idempotency-Key",
        ],
    )
    app.include_router(health_router)
    app.include_router(tenant_router)
    app.include_router(brief_router)
    app.include_router(ingestion_router)
    app.include_router(source_asset_router)
    app.include_router(source_object_router)
    app.include_router(document_extraction_router)

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_correlation_id = request.headers.get("x-correlation-id")
        correlation_id = raw_correlation_id or str(uuid4())
        request.state.correlation_id = correlation_id
        if raw_correlation_id is not None and not CORRELATION_ID_PATTERN.fullmatch(
            raw_correlation_id
        ):
            return error_response(request, 400, "invalid_correlation_id", "Invalid request")
        if not resolved_settings.temporary_identity_headers_enabled and any(
            header in request.headers for header in TEMPORARY_IDENTITY_HEADERS
        ):
            return error_response(
                request,
                403,
                "temporary_identity_disabled",
                "Temporary identity context is disabled",
            )
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                request_limit = (
                    resolved_settings.api_max_upload_bytes
                    if request.url.path.endswith("/uploads")
                    else resolved_settings.api_max_request_bytes
                )
                too_large = int(content_length) > request_limit
            except ValueError:
                return error_response(request, 400, "invalid_request", "Invalid request")
            if too_large:
                return error_response(request, 413, "request_too_large", "Request is too large")
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/api/v1/health", status_code=307)

    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, error: ApplicationError) -> JSONResponse:
        status_code = 400
        if isinstance(error, ResourceNotFound):
            status_code = 404
        elif isinstance(error, ResourceConflict):
            status_code = 409
        elif isinstance(error, TemporaryIdentityDisabled):
            status_code = 403
        elif isinstance(error, StorageUnavailable):
            status_code = 503
        return error_response(request, status_code, error.code, str(error))

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, error: DomainError) -> JSONResponse:
        status_code = (
            409
            if isinstance(
                error,
                (
                    VersionConflict,
                    InvalidProjectTransition,
                    InvalidBriefTransition,
                    ApprovalBlocked,
                ),
            )
            else 400
        )
        if isinstance(
            error, (InvalidProjectMutation, InvalidBriefMutation, InvalidSourceAssetMutation)
        ) and "archived" in str(error):
            status_code = 409
        return error_response(request, status_code, error.code, str(error))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
        return error_response(request, 400, "invalid_request", "Invalid request")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "unhandled API error",
            extra={
                "event": "api.unhandled_error",
                "path": request.url.path,
                "correlation_id": getattr(request.state, "correlation_id", None),
            },
            exc_info=error,
        )
        return error_response(request, 500, "internal_error", "Internal server error")

    return app


app = create_app()


__all__ = ["app", "create_app", "SERVICE_NAME"]
