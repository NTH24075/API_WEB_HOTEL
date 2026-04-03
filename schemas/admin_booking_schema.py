from pydantic import BaseModel
from typing import Optional


class BookingFilterRequest(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    booking_status: Optional[str] = None
    payment_status: Optional[str] = None
    keyword: Optional[str] = None


class BookingResponse(BaseModel):
    booking_id: int
    booking_code: str
    check_in: str
    check_out: str
    total_amount: float
    booking_status: str
    payment_status: str
    customer_name: str
    email: str
    hotel_name: str


class BookingDetailResponse(BaseModel):
    booking_id: int
    booking_code: str
    check_in: str
    check_out: str
    total_amount: float
    booking_status: str
    payment_status: str
    customer_name: str
    email: str
    phone: Optional[str]
    hotel_name: str