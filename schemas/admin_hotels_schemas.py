from pydantic import BaseModel, Field
from typing import Optional


class ImportHotelsByCityRequest(BaseModel):
    city: str = Field(..., min_length=2, max_length=100)
    max_results: int = Field(10, ge=1, le=30)