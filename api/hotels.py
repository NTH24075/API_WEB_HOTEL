from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from core.database import get_conn, query_all
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


def _get_or_create_city_id(cursor, hotel: dict) -> int:
    """
    Tìm CityId phù hợp từ tọa độ hotel, hoặc tạo mới nếu chưa có.
    Ưu tiên lookup theo country_code + tên city từ address.
    """
    # Thử tìm theo tên thành phố trong address (nếu có)
    address = hotel.get("address") or ""
    city_name = None
    # Geoapify thường trả về "..., Thành phố, Quốc gia"
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        city_name = parts[-2]  # phần thứ 2 từ cuối thường là thành phố

    if city_name:
        cursor.execute(
            "SELECT TOP 1 CityId FROM Cities WHERE CityName LIKE ?",
            (f"%{city_name}%",),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # Tìm theo tọa độ gần nhất (trong vòng ~1 độ)
    lat = hotel.get("latitude")
    lon = hotel.get("longitude")
    if lat is not None and lon is not None:
        cursor.execute(
            "SELECT TOP 1 CityId FROM Cities "
            "WHERE ABS(Latitude - ?) < 1.0 AND ABS(Longitude - ?) < 1.0",
            (lat, lon),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # Không tìm thấy → tạo mới City từ thông tin có được
    country_code = hotel.get("country_code") or "VN"
    insert_city_name = city_name or "Unknown City"
    cursor.execute(
        "INSERT INTO Cities (CityName, CountryName, Latitude, Longitude) "
        "OUTPUT INSERTED.CityId "
        "VALUES (?, ?, ?, ?)",
        (insert_city_name, country_code, lat, lon),
    )
    row = cursor.fetchone()
    return row[0] if row else 1


def _sync_hotel_to_db(hotel: dict) -> None:
    """
    Upsert một hotel (từ Geoapify) vào bảng Hotels + HotelImages.
    Chạy trong background thread để không làm chậm response.
    """
    try:
        from Db import query_one, get_connection

        hotel_id = hotel.get("hotel_id") or ""
        if not hotel_id:
            return

        # Upsert Hotels
        existing = query_one(
            "SELECT HotelId FROM Hotels WHERE ExternalHotelCode = ?",
            (hotel_id,),
        )
        if not existing:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Lookup hoặc tạo City trước để tránh FK violation
                city_id = _get_or_create_city_id(cursor, hotel)
                cursor.execute(
                    "INSERT INTO Hotels "
                    "(ExternalHotelCode, CityId, HotelName, Address, Latitude, Longitude, "
                    " StarRating, ThumbnailUrl, Source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'geoapify')",
                    (
                        hotel_id,
                        city_id,
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

@router.get("/api/amenities")
def api_amenities():
    """Trả về danh sách amenities từ bảng Services."""
    try:
        rows = query_all(
            "SELECT ServiceId, ServiceName, IconEmoji, Description "
            "FROM Services WHERE IsActive = 1 ORDER BY ServiceId"
        )
        return [
            {
                "id": r["ServiceId"],
                "name": r["ServiceName"],
                "icon": r.get("IconEmoji") or "",
                "description": r.get("Description") or "",
            }
            for r in rows
        ]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/weather")
def api_weather(
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    city: str | None = Query(None),
    city_code: str | None = Query(None),
    check_in: str | None = Query(None),
    lang: str = Query("vi"),
):
    """Proxy thời tiết — giấu API key khỏi frontend."""
    try:
        return get_weather_forecast_3days(
            lat=lat,
            lon=lon,
            city=city,
            city_code=city_code,
            check_in=check_in,
            lang=lang,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))