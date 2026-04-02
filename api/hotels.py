from fastapi import APIRouter, HTTPException, Query
import traceback
import threading
from services.amadeus_service import (
    get_hotel_detail_payload,
    search_hotels_by_city,
    get_weather_forecast_3days,
    _upsert_hotel_images_to_db,
)

router = APIRouter()


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


@router.get("/api/weather")
def api_weather(
    city: str | None = Query(None),
    city_code: str | None = Query(None),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    check_in: str | None = Query(None),
    lang: str = Query("vi"),
):
    try:
        return get_weather_forecast_3days(
            city=city,
            city_code=city_code,
            lat=lat,
            lon=lon,
            check_in=check_in,
            lang=lang,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint mới: trả về danh sách amenities từ DB ────────────────────────────

@router.get("/api/amenities")
def api_amenities():
    """
    Trả về danh sách tiện nghi (AMEN_LABELS) từ bảng Services trong DB.
    Frontend dùng để render filter checkbox và badge thay vì hardcode.
    Response: [{ "key": "Wi-Fi", "label": "Wi-Fi", "icon": "📶" }, ...]
    """
    try:
        from db import get_amenity_labels_cached
        rows = get_amenity_labels_cached()
        return [
            {
                "key":   row["ServiceName"],
                "label": row["ServiceName"],
                "icon":  row.get("IconEmoji") or "",
            }
            for row in rows
        ]
    except Exception as e:
        traceback.print_exc()
        # Fallback: trả về hardcode nếu DB chưa sẵn sàng
        return [
            {"key": "Wi-Fi",      "label": "Wi-Fi",      "icon": "📶"},
            {"key": "Hồ bơi",     "label": "Hồ bơi",     "icon": "🏊"},
            {"key": "Điều hòa",   "label": "Điều hòa",   "icon": "❄️"},
            {"key": "Bãi đỗ xe",  "label": "Bãi đỗ xe",  "icon": "🅿️"},
            {"key": "Phòng gym",  "label": "Phòng gym",  "icon": "🏋️"},
            {"key": "Spa",        "label": "Spa",         "icon": "💆"},
            {"key": "Nhà hàng",   "label": "Nhà hàng",   "icon": "🍽"},
            {"key": "Thú cưng",   "label": "Thú cưng",   "icon": "🐾"},
        ]


# ── Endpoint mới: trả về danh sách thành phố từ DB ───────────────────────────

@router.get("/api/cities")
def api_cities():
    """
    Trả về danh sách city code aliases từ bảng Cities trong DB.
    Response: [{ "code": "HAN", "name": "Hanoi", "country": "Vietnam" }, ...]
    """
    try:
        from db import query_all
        rows = query_all(
            "SELECT CityCode, CityName, CountryName "
            "FROM Cities WHERE CityCode IS NOT NULL ORDER BY CityName"
        )
        return [
            {
                "code":    row["CityCode"],
                "name":    row["CityName"],
                "country": row["CountryName"],
            }
            for row in rows
        ]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint reload cache (dùng khi admin cập nhật DB) ───────────────────────

@router.post("/api/admin/reload-cache")
def api_reload_cache():
    """
    Xóa lru_cache để lần gọi tiếp theo sẽ đọc lại từ DB.
    Gọi sau khi thêm/sửa Services hoặc Cities trong DB.
    """
    try:
        from db import invalidate_cache
        invalidate_cache()
        return {"status": "ok", "message": "Cache đã được xóa. Dữ liệu sẽ được tải lại từ DB."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))