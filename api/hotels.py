from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from core.database import get_conn
import traceback
import threading
from services.amadeus_service import (
    get_hotel_detail_payload,
    search_hotels_by_city,
    get_weather_forecast_3days,
    _upsert_hotel_images_to_db,
)

class FavoritePayload(BaseModel):
    user_id: int
    hotel_id: str

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _sync_hotel_to_db(hotel: dict) -> None:
    """
    Upsert một hotel (từ Geoapify) vào bảng Hotels + HotelImages.
    Chạy trong background thread để không làm chậm response.
    """
    try:
        from db import query_one, get_connection

        hotel_id = hotel.get("hotel_id") or ""
        if not hotel_id:
            return

        # Upsert Hotels
        existing = query_one(
            "SELECT HotelId FROM Hotels WHERE ExternalHotelCode = ?",
            (hotel_id,),
        )
        if not existing:
            # Lấy CityId mặc định (nếu chưa biết city thì dùng CityId=1)
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO Hotels "
                    "(ExternalHotelCode, CityId, HotelName, Address, Latitude, Longitude, "
                    " StarRating, ThumbnailUrl, Source) "
                    "VALUES (?, 1, ?, ?, ?, ?, ?, ?, 'geoapify')",
                    (
                        hotel_id,
                        hotel.get("name") or "Unknown",
                        hotel.get("address") or "",
                        hotel.get("latitude"),
                        hotel.get("longitude"),
                        hotel.get("stars"),
                        hotel.get("thumbnail") or "",
                    ),
                )
                conn.commit()

        # Upsert HotelImages (thumbnail + gallery)
        _upsert_hotel_images_to_db(hotel_id)

    except Exception as exc:
        print(f"[warn] _sync_hotel_to_db: {exc}")


@router.get("/api/hotels")
def api_list_hotels(
    city_code: str | None = Query(None),
    city: str | None = Query(None),
    max_results: int = Query(12, ge=1, le=200),
):
    try:
        hotels = search_hotels_by_city(
            city_code=city_code,
            city=city,
            max_results=max_results,
        )
        # Sync hotels vào DB trong background — không block response
        def _bg():
            for h in hotels:
                _sync_hotel_to_db(h)
        threading.Thread(target=_bg, daemon=True).start()

        return hotels
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/hotels/{hotel_id}")
def api_hotel_detail(
    hotel_id: str,
    check_in: str = Query("2026-04-08"),
    adults: int = Query(2, ge=1, le=9),
):
    try:
        return get_hotel_detail_payload(
            hotel_id=hotel_id,
            check_in=check_in,
            adults=adults,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hotels/{hotel_id}", response_class=HTMLResponse)
def hotel_detail_page(
    request: Request,
    hotel_id: str,
    check_in: str = Query("2026-04-08"),
    check_out: str = Query("2026-04-09"),
    adults: int = Query(2, ge=1, le=9),
):
    try:
        hotel = get_hotel_detail_payload(
            hotel_id=hotel_id,
            check_in=check_in,
            adults=adults,
        )
        return templates.TemplateResponse(
            request=request,
            name="hotel_detail.html",
            context={
                "hotel": hotel,
                "hotel_id": hotel_id,
                "check_in": check_in,
                "check_out": check_out,
                "adults": adults,
            }
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/favorites")
def add_favorite(payload: FavoritePayload):
    conn = None
    try:
        conn = get_conn()
        curs = conn.cursor()

        user_id = payload.user_id
        hotel_id = payload.hotel_id

        # kiểm tra user tồn tại
        # curs.execute("SELECT UserId FROM Users WHERE UserId = ?", (user_id,))
        # user = curs.fetchone()

        # if not user:
        #     raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

        # kiểm tra đã thích chưa
        curs.execute(
            "SELECT FavoriteId FROM FavoriteHotels WHERE UserId = ? AND HotelId = ?",
            (user_id, hotel_id)
        )
        existed = curs.fetchone()

        if existed:
            raise HTTPException(status_code=400, detail="Khách sạn đã có trong yêu thích")

        # thêm favorite
        curs.execute(
            "INSERT INTO FavoriteHotels (UserId, HotelId) VALUES (?, ?)",
            (user_id, hotel_id)
        )
        conn.commit()

        return {
            "success": True,
            "message": "Đã thêm vào yêu thích!",
            "user_id": user_id,
            "hotel_id": hotel_id
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi server: {str(e)}")
    finally:
        if conn:
            conn.close()





