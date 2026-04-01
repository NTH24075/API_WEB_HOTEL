from pydantic import BaseModel, Field
from typing import Optional, Any


class CurrentUserInfo(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    citizen_id: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    role_name: Optional[str] = None
    status: Optional[str] = None


class RoomOfferInfo(BaseModel):
    OfferId: int
    HotelId: Optional[int] = None
    ExternalOfferCode: Optional[str] = None
    RoomType: Optional[str] = None
    Description: Optional[str] = None
    Capacity: Optional[int] = None
    PricePerNight: Optional[float] = None
    Currency: Optional[str] = None
    AvailableQuantity: Optional[int] = None
    CheckInDate: Optional[Any] = None
    CheckOutDate: Optional[Any] = None
    CancellationPolicy: Optional[str] = None
    Amenities: Optional[str] = None


class CurrentUserAndRoomOfferResponse(BaseModel):
    user: CurrentUserInfo
    room_offer: RoomOfferInfo

class CreateReviewRequest(BaseModel):
    booking_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None