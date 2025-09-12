# Pydantic models (request/response)

from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    location: str | None = None
