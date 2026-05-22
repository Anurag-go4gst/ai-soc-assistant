from pydantic import BaseModel


class GraphEntity(BaseModel):
    entity_id: str
    entity_type: str
    label: str
