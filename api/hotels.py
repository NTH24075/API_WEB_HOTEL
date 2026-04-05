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

def _read_hotels_from_db(city_code: str | None, city: str | None, max_results: int) -> list[dict]:
    rows = []
    try:
        # Truy vấn chính: lấy thông tin hotel kèm rating và giá
        base_select = """
            SELECT TOP (?)
                h.HotelId,
                h.ExternalHotelCode AS hotel_id,
                h.HotelName         AS name,
                h.Address           AS address,
                h.Latitude          AS latitude,
                h.Longitude         AS longitude,
                h.StarRating        AS stars,
                h.ThumbnailUrl      AS thumbnail,
                c.CityCode          AS city_code,
                ISNULL(AVG(CAST(r.Rating AS FLOAT)), 0) AS rating_overall,
                ISNULL(MIN(ro.PricePerNight), 0)        AS price_from
            FROM Hotels h
            JOIN Cities c ON h.CityId = c.CityId
            LEFT JOIN Reviews r  ON r.HotelId  = h.HotelId
            LEFT JOIN RoomOffers ro ON ro.HotelId = h.HotelId
        """

        group_order = """
            GROUP BY
                h.HotelId, h.ExternalHotelCode, h.HotelName,
                h.Address, h.Latitude, h.Longitude,
                h.StarRating, h.ThumbnailUrl, c.CityCode
            ORDER BY h.HotelId DESC
        """

        if city_code:
            rows = query_all(
                base_select + " WHERE c.CityCode = ? " + group_order,
                (max_results, city_code.upper())
            )

        if not rows and city:
            rows = query_all(
                base_select + " WHERE c.CityName LIKE ? " + group_order,
                (max_results, f"%{city}%")
            )

    except Exception as exc:
        print(f"[warn] _read_hotels_from_db: {exc}")
        return []

    if not rows:
        return []

    # Lấy danh sách HotelId để query amenities một lần duy nhất (tránh N+1)
    hotel_ids = [r["HotelId"] for r in rows]
    amenities_map: dict[int, list[str]] = {}
    try:
        placeholders = ",".join(["?"] * len(hotel_ids))
        amen_rows = query_all(
            f"""
            SELECT hs.HotelId, s.ServiceName, s.IconEmoji
            FROM HotelServices hs
            JOIN Services s ON s.ServiceId = hs.ServiceId
            WHERE hs.HotelId IN ({placeholders}) AND s.IsActive = 1
            ORDER BY hs.HotelId, s.ServiceId
            """,
            tuple(hotel_ids),
        )
        for ar in amen_rows:
            hid = ar["HotelId"]
            label = f"{ar.get('IconEmoji', '')} {ar['ServiceName']}".strip()
            amenities_map.setdefault(hid, []).append(label)
    except Exception as exc:
        print(f"[warn] amenities query failed: {exc}")

    return [
        {
            "hotel_id":          r["hotel_id"] or str(r["HotelId"]),
            "name":              r["name"] or "Unknown",
            "address":           r["address"] or "",
            "city_code":         r["city_code"],
            "country_code":      None,
            "latitude":          float(r["latitude"])  if r["latitude"]  is not None else None,
            "longitude":         float(r["longitude"]) if r["longitude"] is not None else None,
            "thumbnail":         r["thumbnail"] or "",
            "stars":             int(round(float(r["stars"]))) if r["stars"] is not None else 3,
            "price_from":        float(r["price_from"]),
            "rating_overall":    round(float(r["rating_overall"]), 1),
            # Trả về service IDs (numeric) để filter JS khớp với checkbox value từ /api/amenities
            "amenities_preview": amenities_map.get(r["HotelId"], []),
        }
        for r in rows
    ]

# ── BUG FIX #1: Chỉ đọc từ DB, không fallback ra external API ─────────────────
@router.get("/api/hotels")
def api_list_hotels(
    city_code: str | None = Query(None),
    city: str | None = Query(None),
    max_results: int = Query(12, ge=1, le=200),
):
    """
    Luôn đọc từ DB nội bộ.
    Admin dùng /admin/hotels/import để đưa dữ liệu vào trước.
    """
    try:
        db_hotels = _read_hotels_from_db(city_code, city, max_results)
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