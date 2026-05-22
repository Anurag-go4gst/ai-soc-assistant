from pydantic import BaseModel


class PlaceholderResponse(BaseModel):
    trace_id: str
    message: str
    note: str
