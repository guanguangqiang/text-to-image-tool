from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Application factory used by the server and the test suite."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application_started name=%s environment=%s",
            settings.app_name,
            settings.environment,
        )
        yield
        logger.info("application_stopped name=%s", settings.app_name)

    docs_enabled = settings.environment != "production" or settings.debug
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    application.state.settings = settings

    application.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
