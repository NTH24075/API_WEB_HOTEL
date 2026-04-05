from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ImportHotelsByCityRequest(BaseModel):
    city: str = Field(..., min_length=2, max_length=100)
    max_results: int = Field(10, ge=1, le=30)


class AdminHotelSearchRequest(BaseModel):
    city: Optional[str] = None
    hotel_name: Optional[str] = None

    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)

    min_rating: Optional[float] = Field(None, ge=1, le=5)
    max_rating: Optional[float] = Field(None, ge=1, le=5)

    min_capacity: Optional[int] = Field(None, ge=1)
    min_available_quantity: Optional[int] = Field(None, ge=0)

    source: Optional[str] = None

    sort_by: Literal["price_asc", "price_desc", "rating_desc", "newest"] = "price_asc"

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price không được lớn hơn max_price")

        if self.min_rating is not None and self.max_rating is not None:
            if self.min_rating > self.max_rating:
                raise ValueError("min_rating không được lớn hơn max_rating")

        return self