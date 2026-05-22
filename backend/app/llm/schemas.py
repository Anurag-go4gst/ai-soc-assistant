from pydantic import BaseModel


class LlmRequest(BaseModel):
    task_type: str
    context: str
