from fastapi import APIRouter

from app.schemas.common import MessageRequest, MessageResponse

router = APIRouter()


@router.get("/ping", response_model=MessageResponse)
async def ping() -> MessageResponse:
    return MessageResponse(message="pong")


@router.post("/echo", response_model=MessageResponse)
async def echo(payload: MessageRequest) -> MessageResponse:
    """A small example showing request validation and response schemas."""
    return MessageResponse(message=payload.message)
