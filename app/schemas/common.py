from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class MessageResponse(BaseModel):
    message: str
