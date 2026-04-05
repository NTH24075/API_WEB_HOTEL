from fastapi import APIRouter, Depends, Query
from core.dependencies import require_receptionist
from services.receptionist_booking_service import (
    get_my_hotel_bookings,
    get_my_hotel_booking_detail,
    check_in_my_hotel_booking,
    check_out_my_hotel_booking,
    cancel_my_hotel_booking,
    get_my_hotel_payments
)

router = APIRouter(prefix="/receptionist/bookings", tags=["Receptionist Booking"])


# =========================
# LIST + FILTER BOOKING
# =========================
@router.get("")
def get_bookings(
    from_date: str = Query(None),
    to_date: str = Query(None),
    booking_status: str = Query(None),
    payment_status: str = Query(None),
    keyword: str = Query(None),
    receptionist=Depends(require_receptionist)
):
    return get_my_hotel_bookings(
        user_id=receptionist["user_id"],
        from_date=from_date,
        to_date=to_date,
        booking_status=booking_status,
        payment_status=payment_status,
        keyword=keyword
    )


# =========================
# BOOKING DETAIL
# =========================
@router.get("/{booking_id}")
def booking_detail(
    booking_id: int,
    receptionist=Depends(require_receptionist)
):
    return get_my_hotel_booking_detail(
        user_id=receptionist["user_id"],
        booking_id=booking_id
    )


# =========================
# CHECK-IN
# =========================
@router.post("/{booking_id}/check-in")
def check_in(
    booking_id: int,
    receptionist=Depends(require_receptionist)
):
    return check_in_my_hotel_booking(
        user_id=receptionist["user_id"],
        booking_id=booking_id
    )


# =========================
# CHECK-OUT
# =========================
@router.post("/{booking_id}/check-out")
def check_out(
    booking_id: int,
    receptionist=Depends(require_receptionist)
):
    return check_out_my_hotel_booking(
        user_id=receptionist["user_id"],
        booking_id=booking_id
    )


# =========================
# CANCEL BOOKING
# =========================
@router.post("/{booking_id}/cancel")
def cancel(
    booking_id: int,
    receptionist=Depends(require_receptionist)
):
    return cancel_my_hotel_booking(
        user_id=receptionist["user_id"],
        booking_id=booking_id
    )


# =========================
# PAYMENT LIST
# =========================
@router.get("/payments/all")
def payments(receptionist=Depends(require_receptionist)):
    return get_my_hotel_payments(user_id=receptionist["user_id"])