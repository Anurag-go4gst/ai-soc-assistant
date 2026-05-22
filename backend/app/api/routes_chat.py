from uuid import uuid4

from fastapi import APIRouter

from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

router = APIRouter()


@router.post("/chat", response_model=PlaceholderResponse)
def chat(request: ChatRequest) -> PlaceholderResponse:
    return PlaceholderResponse(
        trace_id=str(uuid4()),
        message=f"Received placeholder chat request: {request.message}",
        note="LangGraph orchestration is not implemented yet.",
    )
