from fastapi import APIRouter, Depends, Query
from core.dependencies import require_admin

from services.admin_hotel_service import (
    get_all_bookings,
    get_booking_detail,
    check_in_booking,
    check_out_booking,
    cancel_booking,
    get_all_payments
)


router = APIRouter(prefix="/admin/bookings", tags=["Admin Booking"])


# 🔥 list + filter
@router.get("")
def get_bookings(
    from_date: str = Query(None),
    to_date: str = Query(None),
    booking_status: str = Query(None),
    payment_status: str = Query(None),
    keyword: str = Query(None),
    admin=Depends(require_admin)
):
    return get_all_bookings(
        from_date,
        to_date,
        booking_status,
        payment_status,
        keyword
    )


# 🔥 detail
@router.get("/{booking_id}")
def booking_detail(
    booking_id: int,
    admin=Depends(require_admin)
):
    return get_booking_detail(booking_id)


# 🔥 check-in
@router.post("/{booking_id}/check-in")
def check_in(
    booking_id: int,
    admin=Depends(require_admin)
):
    return check_in_booking(booking_id)


# 🔥 check-out
@router.post("/{booking_id}/check-out")
def check_out(
    booking_id: int,
    admin=Depends(require_admin)
):
    return check_out_booking(booking_id)


# 🔥 cancel
@router.post("/{booking_id}/cancel")
def cancel(
    booking_id: int,
    admin=Depends(require_admin)
):
    return cancel_booking(booking_id)


# 🔥 payment list
@router.get("/payments/all")
def payments(admin=Depends(require_admin)):
    return get_all_payments()