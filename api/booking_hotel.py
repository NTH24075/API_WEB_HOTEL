from fastapi import APIRouter, Depends, HTTPException, Query
from core.database import get_conn
from core.dependencies import get_current_user

router = APIRouter(prefix="/booking-review", tags=["Booking Review"])


def get_user_by_id(curs, user_id: int):
    curs.execute("""
        SELECT UserId, FullName, Email, Phone, Address, AvatarUrl
        FROM Users
        WHERE UserId = ?
    """, (user_id,))
    row = curs.fetchone()

    if not row:
        return None

    return {
        "user_id": row.UserId,
        "full_name": row.FullName,
        "email": row.Email,
        "phone": row.Phone,
        "address": row.Address,
        "avatar_url": row.AvatarUrl
    }


def get_room_offer_by_id(curs, offer_id: int):
    curs.execute("""
        SELECT 
            OfferId,
            HotelId,
            ExternalOfferCode,
            RoomType,
            Description,
            Capacity,
            PricePerNight,
            Currency,
            AvailableQuantity,
            CheckInDate,
            CheckOutDate,
            CancellationPolicy,
            Amenities
        FROM RoomOffers
        WHERE OfferId = ?
    """, (offer_id,))
    row = curs.fetchone()

    if not row:
        return None

    return {
        "offer_id": row.OfferId,
        "hotel_id": row.HotelId,
        "external_offer_code": row.ExternalOfferCode,
        "room_type": row.RoomType,
        "description": row.Description,
        "capacity": row.Capacity,
        "price_per_night": float(row.PricePerNight) if row.PricePerNight else 0,
        "currency": row.Currency,
        "available_quantity": row.AvailableQuantity,
        "check_in_date": str(row.CheckInDate) if row.CheckInDate else None,
        "check_out_date": str(row.CheckOutDate) if row.CheckOutDate else None,
        "cancellation_policy": row.CancellationPolicy,
        "amenities": row.Amenities
    }


@router.get("/review")
def booking_review(
    offer_id: int = Query(...),
    current_user=Depends(get_current_user)
):
    conn = get_conn()
    try:
        curs = conn.cursor()

        # lấy user id từ user đang đăng nhập
        user_id = current_user["UserId"] if isinstance(current_user, dict) else current_user.UserId

        user = get_user_by_id(curs, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy user")

        room_offer = get_room_offer_by_id(curs, offer_id)
        if not room_offer:
            raise HTTPException(status_code=404, detail="Không tìm thấy room offer")

        return {
            "user": user,
            "room_offer": room_offer
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi booking review: {str(e)}")
    finally:
        conn.close()