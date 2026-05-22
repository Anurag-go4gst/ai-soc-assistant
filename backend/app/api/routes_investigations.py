from uuid import uuid4

from fastapi import APIRouter, Depends

from app.auth.session import require_auth
from app.schemas.requests import InvestigationRequest
from app.schemas.responses import PlaceholderResponse

router = APIRouter()


@router.post("/investigate", response_model=PlaceholderResponse, dependencies=[Depends(require_auth)])
def investigate(request: InvestigationRequest) -> PlaceholderResponse:
    return PlaceholderResponse(
        trace_id=str(uuid4()),
        message=f"Received placeholder investigation request: {request.alert_id}",
        note="Splunk MCP is not connected yet.",
    )
