from fastapi import APIRouter, Request, status

from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
)
async def ready(request: Request) -> HealthResponse:
    # Add database/cache checks here when those dependencies are introduced.
    return await health(request)
