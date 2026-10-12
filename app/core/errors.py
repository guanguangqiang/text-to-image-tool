from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Expected application error that can be safely returned to a client."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def _error_content(
    request: Request,
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, Any]:
    content: dict[str, Any] = {
        "error": {"code": code, "message": message},
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        content["error"]["details"] = details
    return content


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_content(
            request,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_content(
            request,
            code="validation_error",
            message="Request validation failed",
            details=exc.errors(),
        ),
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception request_id=%s path=%s",
        getattr(request.state, "request_id", "unknown"),
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_content(
            request,
            code="internal_server_error",
            message="An unexpected error occurred",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
