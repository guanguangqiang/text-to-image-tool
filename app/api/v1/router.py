from fastapi import APIRouter

from app.api.v1.routes.examples import router as examples_router

router = APIRouter()
router.include_router(examples_router, prefix="/examples", tags=["examples"])
