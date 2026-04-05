from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from core.database import get_conn, query_all
import os
import traceback
import threading
from services.amadeus_service import (
    get_hotel_detail_payload,
    search_hotels_by_city,
    get_weather_forecast_3days,
    _upsert_hotel_images_to_db,
)
from services.hotel_pricing_service import get_default_price_from

class FavoritePayload(BaseModel):
    user_id: int
    hotel_id: str

router = APIRouter()
templates = Jinja2Templates(directory="templates")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")


def _fallback_price_from(hotel_db_id: int, stars: float | int | None) -> float:
    return float(get_default_price_from(int(hotel_db_id)))


def _get_or_create_city_id(cursor, hotel: dict) -> int:
    """
    Tìm CityId phù hợp từ tọa độ hotel, hoặc tạo mới nếu chưa có.
    Ưu tiên lookup theo country_code + tên city từ address.
    """
    address = hotel.get("address") or ""
    city_name = None
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        city_name = parts[-2]

    if city_name:
        cursor.execute(
            "SELECT TOP 1 CityId FROM Cities WHERE CityName LIKE ?",
            (f"%{city_name}%",),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

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
def _read_hotels_from_db(
    city_code: str | None,
    city: str | None,
    max_results: int,
    keyword: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    rows = []
    try:
        base_select = """
            SELECT TOP (200)
                h.HotelId           AS hotel_db_id,
                h.ExternalHotelCode AS hotel_id,
                h.HotelName         AS name,
                h.Address           AS address,
                h.Latitude          AS latitude,
                h.Longitude         AS longitude,
                h.StarRating        AS stars,
                h.ThumbnailUrl      AS thumbnail,
                c.CityCode          AS city_code,
                ISNULL((
                    SELECT AVG(CAST(r.Rating AS FLOAT))
                    FROM Reviews r
                    WHERE r.HotelId = h.HotelId
                ), 0) AS rating_overall,
                (
                    SELECT MIN(ro.PricePerNight)
                    FROM RoomOffers ro
                    WHERE ro.HotelId = h.HotelId
                ) AS price_from
            FROM Hotels h
            JOIN Cities c ON h.CityId = c.CityId
        """

        if keyword:
            kw = keyword.strip()
            kw_like = f"%{kw}%"
            city_code_guess = kw.upper() if len(kw) == 3 and kw.isalpha() else None
            sql = base_select + """
                WHERE (
                    LOWER(h.HotelName) LIKE LOWER(?)
                    OR LOWER(ISNULL(h.Address, '')) LIKE LOWER(?)
                    OR LOWER(c.CityName) LIKE LOWER(?)
            """
            params: list = [kw_like, kw_like, kw_like]
            if city_code_guess:
                sql += " OR c.CityCode = ? "
                params.append(city_code_guess)
            sql += ") ORDER BY h.HotelId DESC"
            rows = query_all(sql, tuple(params))
        elif city_code:
            rows = query_all(
                base_select + " WHERE c.CityCode = ? ORDER BY h.HotelId DESC",
                (city_code.upper(),)
            )

        if not rows and city:
            rows = query_all(
                base_select + " WHERE c.CityName LIKE ? ORDER BY h.HotelId DESC",
                (f"%{city}%",)
            )

    except Exception as exc:
        print(f"[warn] _read_hotels_from_db: {exc}")
        return []

    if not rows:
        return []

    hotel_ids = [r["hotel_db_id"] for r in rows]
    amenities_map = {}

    try:
        placeholders = ",".join(["?"] * len(hotel_ids))
        amen_rows = query_all(
            f"""
            SELECT hs.HotelId, s.ServiceName, s.IconEmoji
            FROM HotelServices hs
            JOIN Services s ON s.ServiceId = hs.ServiceId
            WHERE hs.HotelId IN ({placeholders})
              AND hs.IsAvailable = 1
              AND s.IsActive = 1
            ORDER BY hs.HotelId, s.ServiceId
            """,
            tuple(hotel_ids),
        )
        for ar in amen_rows:
            hid = ar["HotelId"]
            icon = (ar.get("IconEmoji") or "").strip()
            label = f"{icon} {ar['ServiceName']}".strip()
            amenities_map.setdefault(hid, []).append(label)
    except Exception as exc:
        print(f"[warn] amenities query failed: {exc}")

    hotels = []
    for r in rows:
        stars = int(round(float(r["stars"]))) if r["stars"] is not None else 3
        price_from = (
            float(r["price_from"])
            if r["price_from"] is not None
            else _fallback_price_from(r["hotel_db_id"], stars)
        )
        hotels.append(
            {
                "hotel_id":          r["hotel_id"] or str(r["hotel_db_id"]),
                "hotel_db_id":       int(r["hotel_db_id"]),
                "name":              r["name"] or "Unknown",
                "address":           r["address"] or "",
                "city_code":         r["city_code"],
                "country_code":      None,
                "latitude":          float(r["latitude"]) if r["latitude"] is not None else None,
                "longitude":         float(r["longitude"]) if r["longitude"] is not None else None,
                "thumbnail":         r["thumbnail"] or "",
                "stars":             stars,
                "price_from":        price_from,
                "rating_overall":    round(float(r["rating_overall"]), 1),
                "amenities_preview": amenities_map.get(r["hotel_db_id"], []),
            }
        )
    if max_price is not None:
        hotels = [hotel for hotel in hotels if hotel["price_from"] is not None and hotel["price_from"] <= max_price]

    return hotels[:max_results]

# ── BUG FIX #1: Chỉ đọc từ DB, không fallback ra external API ─────────────────
@router.get("/api/hotels")
def api_list_hotels(
    city_code: str | None = Query(None),
    city: str | None = Query(None),
    keyword: str | None = Query(None),
    max_price: float | None = Query(None, ge=0),
    max_results: int = Query(12, ge=1, le=200),
):
    """
    Luôn đọc từ DB nội bộ.
    Admin dùng /admin/hotels/import để đưa dữ liệu vào trước.
    """
    try:
        db_hotels = _read_hotels_from_db(
            city_code=city_code,
            city=city,
            keyword=keyword,
            max_price=max_price,
            max_results=max_results,
        )
        return db_hotels   # trả về list rỗng nếu chưa có → frontend hiện "không tìm thấy"

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
        return templates.TemplateResponse(
            request=request,
            name="hotel_detail.html",
            context={
                "hotel_id": hotel_id,
                "check_in": check_in,
                "check_out": check_out,
                "adults": adults,
                "mapbox_token": MAPBOX_TOKEN,
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

        curs.execute(
            "SELECT FavoriteId FROM FavoriteHotels WHERE UserId = ? AND HotelId = ?",
            (user_id, hotel_id)
        )
        existed = curs.fetchone()

        if existed:
            raise HTTPException(status_code=400, detail="Khách sạn đã có trong yêu thích")

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
