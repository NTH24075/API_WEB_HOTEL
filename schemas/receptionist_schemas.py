from pydantic import BaseModel, Field
from typing import Optional, List


class AssignHotelServiceRequest(BaseModel):
    service_id: int = Field(..., gt=0)
    custom_price: Optional[float] = Field(None, ge=0)
    is_available: bool = True


class UpdateHotelServiceRequest(BaseModel):
    custom_price: Optional[float] = Field(None, ge=0)
    is_available: Optional[bool] = None


class HotelServiceItemResponse(BaseModel):
    hotel_service_id: int
    hotel_id: int
    service_id: int
    service_name: str
    description: Optional[str] = None
    default_price: float
    custom_price: Optional[float] = None
    final_price: float
    unit: Optional[str] = None
    is_active: bool
    is_available: bool


class ReceptionistHotelInfoResponse(BaseModel):
    hotel_id: int
    hotel_name: str
    address: Optional[str] = None


class ReceptionistHotelServicesResponse(BaseModel):
    hotel: ReceptionistHotelInfoResponse
    items: List[HotelServiceItemResponse]