from pydantic import BaseModel
from typing import Optional, List


class BookingFilterRequest(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    booking_status: Optional[str] = None
    payment_status: Optional[str] = None
    keyword: Optional[str] = None


class ReceptionistHotelInfoResponse(BaseModel):
    hotel_id: int
    hotel_name: str
    address: Optional[str] = None


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


class BookingListResponse(BaseModel):
    hotel: ReceptionistHotelInfoResponse
    message: str
    total: int
    data: List[BookingResponse]


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


class PaymentResponse(BaseModel):
    payment_id: int
    amount: float
    payment_status: str
    payment_method: Optional[str] = None
    paid_at: Optional[str] = None
    booking_code: str
    customer_name: str


class PaymentListResponse(BaseModel):
    hotel: ReceptionistHotelInfoResponse
    message: str
    data: List[PaymentResponse]