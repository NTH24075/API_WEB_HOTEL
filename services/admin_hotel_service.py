import os
import random
from typing import Optional
from warnings import filters

import requests
from dotenv import load_dotenv
from fastapi import HTTPException, params

from core.database import get_conn
from services.hotel_pricing_service import build_default_room_offers

load_dotenv()

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
GEOAPIFY_BASE_URL = os.getenv("GEOAPIFY_BASE_URL", "https://api.geoapify.com")


def normalize_nullable_text(value, use_placeholder: bool = False):
    if value is None:
        return "Đang cập nhật" if use_placeholder else None

    text = str(value).strip()
    if text == "":
        return "Đang cập nhật" if use_placeholder else None

    return text

def normalize_phone_text(value, use_placeholder: bool = False, max_length: int = 20):
    text = normalize_nullable_text(value, use_placeholder=False)
    if text is None:
        return "Äang cáº­p nháº­t" if use_placeholder else None

    first = text.split(";")[0].split(",")[0].strip()
    if not first:
        return "Äang cáº­p nháº­t" if use_placeholder else None
    return first[:max_length]


def normalize_email_text(value, use_placeholder: bool = False, max_length: int = 100):
    text = normalize_nullable_text(value, use_placeholder=False)
    if text is None:
        return "Äang cáº­p nháº­t" if use_placeholder else None

    first = text.split(";")[0].split(",")[0].strip()
    if not first:
        return "Äang cáº­p nháº­t" if use_placeholder else None
    return first[:max_length]


def normalize_star_rating(value, default: float = 3.0):
    if value is None:
        return default

    try:
        rating = float(value)

        if rating < 1:
            return 1.0
        if rating > 5:
            return 5.0

        return round(rating, 1)
    except (TypeError, ValueError):
        return default

def geocode_city(city: str):
    if not GEOAPIFY_API_KEY:
        raise Exception("Thiếu GEOAPIFY_API_KEY trong file .env")

    url = f"{GEOAPIFY_BASE_URL}/v1/geocode/search"
    params = {
        "text": city,
        "limit": 1,
        "apiKey": GEOAPIFY_API_KEY
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    features = data.get("features", [])

    if not features:
        raise Exception(f"Không tìm thấy thông tin thành phố: {city}")

    props = features[0].get("properties", {})

    return {
        "city_name": props.get("city") or city,
        "country_name": props.get("country") or "Unknown",
        "lat": props.get("lat"),
        "lon": props.get("lon")
    }


def search_hotels_from_geoapify(city: str, max_results: int = 10):
    geo = geocode_city(city)

    lat = geo["lat"]
    lon = geo["lon"]

    if lat is None or lon is None:
        raise Exception("Không lấy được tọa độ thành phố")

    url = f"{GEOAPIFY_BASE_URL}/v2/places"
    params = {
        "categories": "accommodation.hotel",
        "filter": f"circle:{lon},{lat},5000",
        "bias": f"proximity:{lon},{lat}",
        "limit": max_results,
        "apiKey": GEOAPIFY_API_KEY
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    features = data.get("features", [])

    hotels = []

    for item in features:
        props = item.get("properties", {}) or {}

        datasource = props.get("datasource", {}) or {}
        raw = datasource.get("raw", {}) if isinstance(datasource, dict) else {}

        contact = props.get("contact", {})
        if not isinstance(contact, dict):
            contact = {}

        external_hotel_code = None
        if props.get("place_id") is not None:
            external_hotel_code = str(props.get("place_id"))
        elif raw.get("osm_id") is not None:
            external_hotel_code = str(raw.get("osm_id"))

        hotels.append({
            "external_hotel_code": external_hotel_code,
            "hotel_name": props.get("name") or "Unnamed hotel",
            "address": props.get("formatted") or props.get("address_line2") or None,
            "latitude": props.get("lat"),
            "longitude": props.get("lon"),
            "phone": contact.get("phone"),
            "email": contact.get("email"),
            "thumbnail_url": None,
            "source": "Geoapify",
            "star_rating": normalize_star_rating(
                props.get("stars") or raw.get("stars") or raw.get("hotel_stars"),
                # ── BUG FIX #2: khi Geoapify không trả về sao, random 1-5 dựa vào external_hotel_code
                # để mỗi khách sạn có sao cố định, không bị đổi mỗi lần import
                None  # sẽ xử lý bên dưới
            )
        })

        # Ghi đè star_rating: nếu Geoapify không có → random seed từ external_hotel_code
        h = hotels[-1]
        api_stars = props.get("stars") or raw.get("stars") or raw.get("hotel_stars")
        if api_stars is not None:
            h["star_rating"] = normalize_star_rating(api_stars, 3.0)
        else:
            seed_str = external_hotel_code or (props.get("name") or "hotel")
            seed = sum(ord(c) for c in seed_str)
            h["star_rating"] = float((seed % 5) + 1)   # 1.0 ~ 5.0

    return {
        "city_name": geo["city_name"],
        "country_name": geo["country_name"],
        "latitude": geo["lat"],
        "longitude": geo["lon"],
        "hotels": hotels
    }

def generate_city_code(city_name: str) -> str:
    words = [w for w in city_name.strip().upper().split() if w]
    if not words:
        return "UNK"
    if len(words) == 1:
        return words[0][:3]
    code = "".join(word[0] for word in words[:3])
    return code[:3]


def get_or_create_city(cursor, city_name: str, country_name: str, latitude=None, longitude=None):
    cursor.execute(
        """
        SELECT TOP 1 CityId
        FROM Cities
        WHERE CityName = ? AND CountryName = ?
        """,
        (city_name, country_name)
    )
    row = cursor.fetchone()

    if row:
        if hasattr(row, "CityId"):
            city_id = row.CityId
        else:
            city_id = row[0]

        cursor.execute(
            """
            UPDATE Cities
            SET Latitude = ISNULL(Latitude, ?),
                Longitude = ISNULL(Longitude, ?),
                CityCode = ISNULL(CityCode, ?)
            WHERE CityId = ?
            """,
            (latitude, longitude, generate_city_code(city_name), city_id)
        )
        return city_id

    city_code = generate_city_code(city_name)

    cursor.execute(
        """
        INSERT INTO Cities (CityName, CountryName, CityCode, Latitude, Longitude)
        OUTPUT INSERTED.CityId
        VALUES (?, ?, ?, ?, ?)
        """,
        (city_name, country_name, city_code, latitude, longitude)
    )
    new_row = cursor.fetchone()
    return new_row.CityId if hasattr(new_row, "CityId") else new_row[0]

def find_existing_hotel(
    cursor,
    external_hotel_code: Optional[str],
    hotel_name: str,
    address: Optional[str],
    city_id: int,
    latitude=None,
    longitude=None,
):  # 1. Match theo ExternalHotelCode (chính xác nhất)
    if external_hotel_code:
        cursor.execute(
            """
            SELECT TOP 1 HotelId
            FROM Hotels
            WHERE ExternalHotelCode = ?
            """,
            (external_hotel_code,)
        )
        row = cursor.fetchone()
        if row:
            return row.HotelId

    # 2. Match theo tên + địa chỉ + city
    if address is None:
        cursor.execute(
            """
            SELECT TOP 1 HotelId
            FROM Hotels
            WHERE HotelName = ? AND Address IS NULL AND CityId = ?
            """,
            (hotel_name, city_id)
        )
    else:
        cursor.execute(
            """
            SELECT TOP 1 HotelId
            FROM Hotels
            WHERE HotelName = ? AND Address = ? AND CityId = ?
            """,
            (hotel_name, address, city_id)
        )

    row = cursor.fetchone()
    if row:
        return row.HotelId

    # 3. Match theo tọa độ gần (trong vòng ~50m) — tránh trùng khi place_id thay đổi
    if latitude is not None and longitude is not None:
        cursor.execute(
            """
            SELECT TOP 1 HotelId
            FROM Hotels
            WHERE ABS(Latitude - ?) < 0.0005
              AND ABS(Longitude - ?) < 0.0005
              AND CityId = ?
            """,
            (latitude, longitude, city_id)
        )
        row = cursor.fetchone()
        if row:
            return row.HotelId

    return None


# ── BUG FIX #2: Bảng phòng với giá phong phú, random dựa vào hotel_id ────────
_ROOM_TEMPLATES = [
    # (room_type, description, capacity, base_price, beds, policy)
    ("Phòng Standard",      "Phòng tiêu chuẩn, trang bị đầy đủ tiện nghi cơ bản.",          2,  600_000,  "1 giường đôi, wifi, máy lạnh",          "Miễn phí hủy trước 24h."),
    ("Phòng Superior",      "Phòng rộng hơn Standard, có ban công nhìn ra thành phố.",       2,  900_000,  "1 giường queen, wifi, máy lạnh, TV",     "Miễn phí hủy trước 48h."),
    ("Phòng Deluxe",        "Phòng cao cấp, nội thất sang trọng, tầm nhìn đẹp.",             2, 1_400_000, "1 giường king, wifi, bồn tắm",           "Miễn phí hủy trước 48h."),
    ("Phòng Deluxe Twin",   "Dành cho 2 người, 2 giường đơn thoải mái.",                     2, 1_200_000, "2 giường đơn, wifi, máy lạnh",           "Miễn phí hủy trước 24h."),
    ("Phòng Family",        "Rộng rãi, phù hợp gia đình có trẻ nhỏ.",                        4, 1_800_000, "1 giường king + 2 giường đơn, wifi",     "Không hoàn tiền sau khi đặt."),
    ("Phòng Suite",         "Suite hạng sang, phòng khách riêng, minibar.",                  2, 3_200_000, "1 giường king, phòng khách, bồn sục",    "Miễn phí hủy trước 72h."),
    ("Phòng Junior Suite",  "Không gian mở, khu vực nghỉ ngơi và làm việc tách biệt.",       2, 2_100_000, "1 giường king, sofa, wifi tốc độ cao",   "Miễn phí hủy trước 48h."),
    ("Phòng Executive",     "Dành cho khách công tác, có khu vực làm việc chuyên nghiệp.",   2, 1_600_000, "1 giường king, bàn làm việc, wifi",      "Miễn phí hủy trước 24h."),
    ("Phòng Connecting",    "2 phòng liền nhau, lý tưởng cho nhóm hoặc gia đình lớn.",       4, 2_400_000, "2 giường đôi kết nối, wifi",             "Miễn phí hủy trước 48h."),
    ("Phòng Penthouse",     "Penthouse tầng thượng, tầm nhìn toàn cảnh 360 độ.",             2, 5_500_000, "1 giường king, sân thượng riêng, bồn sục", "Không hoàn tiền sau khi đặt."),
]

def _random_price_multiplier(hotel_id: int) -> float:
    """Tạo hệ số nhân giá ngẫu nhiên nhưng cố định cho từng hotel (seed từ hotel_id)."""
    rng = random.Random(hotel_id * 1337 + 42)
    return round(rng.uniform(0.7, 1.8), 2)   # ×0.70 ~ ×1.80

def create_default_room_offers(cursor, hotel_id: int):
    """
    Tạo 3-5 loại phòng cho khách sạn mới import.
    Giá được random dựa vào hotel_id để mỗi khách sạn có bộ giá khác nhau
    nhưng nhất quán (chạy lại không đổi).
    """
    rng = random.Random(hotel_id * 7919 + 13)

    # Chọn ngẫu nhiên 3-5 loại phòng, không trùng
    num_rooms = rng.randint(3, 5)
    chosen = rng.sample(_ROOM_TEMPLATES, k=min(num_rooms, len(_ROOM_TEMPLATES)))

    multiplier = _random_price_multiplier(hotel_id)

    for room_type, description, capacity, base_price, amenities, policy in chosen:
        # Làm tròn giá đến 50.000
        raw_price = base_price * multiplier
        price = round(raw_price / 50_000) * 50_000
        price = max(300_000, price)   # tối thiểu 300k

        available_qty = rng.randint(1, 8)

        cursor.execute(
            """
            INSERT INTO RoomOffers (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hotel_id,
                None,
                room_type,
                description,
                capacity,
                price,
                "VND",
                available_qty,
                None,
                None,
                policy,
                amenities
            )
        )


def ensure_hotel_supporting_data(cursor, hotel_id: int) -> None:
    cursor.execute(
        "SELECT TOP 1 1 AS ok FROM RoomOffers WHERE HotelId = ?",
        (hotel_id,),
    )
    if not cursor.fetchone():
        create_default_room_offers(cursor, hotel_id)

    cursor.execute(
        "SELECT TOP 1 1 AS ok FROM HotelServices WHERE HotelId = ?",
        (hotel_id,),
    )
    if not cursor.fetchone():
        assign_default_services(cursor, hotel_id)


def assign_default_services(cursor, hotel_id: int) -> None:
    """
    Gán tất cả Services đang active vào HotelServices cho hotel mới.
    Dùng INSERT WHERE NOT EXISTS để idempotent (an toàn khi gọi nhiều lần).
    """
    cursor.execute("SELECT ServiceId FROM Services WHERE IsActive = 1")
    rows = cursor.fetchall()
    for row in rows:
        sid = row[0] if not hasattr(row, "ServiceId") else row.ServiceId
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM HotelServices WHERE HotelId = ? AND ServiceId = ?
            )
            INSERT INTO HotelServices (HotelId, ServiceId, IsAvailable)
            VALUES (?, ?, 1)
            """,
            (hotel_id, sid, hotel_id, sid),
        )


def backfill_hotel_services_and_rooms() -> dict:
    """
    Backfill HotelServices và RoomOffers cho TẤT CẢ hotels cũ chưa có.
    Gọi từ endpoint /admin/hotels/backfill.
    """
    conn = get_conn()
    try:
        cursor = conn.cursor()

        # Hotels chưa có bất kỳ HotelService nào
        cursor.execute(
            """
            SELECT h.HotelId FROM Hotels h
            WHERE NOT EXISTS (
                SELECT 1 FROM HotelServices hs WHERE hs.HotelId = h.HotelId
            )
            """
        )
        hotels_no_services = [r[0] for r in cursor.fetchall()]

        # Hotels chưa có bất kỳ RoomOffer nào
        cursor.execute(
            """
            SELECT h.HotelId FROM Hotels h
            WHERE NOT EXISTS (
                SELECT 1 FROM RoomOffers ro WHERE ro.HotelId = h.HotelId
            )
            """
        )
        hotels_no_rooms = [r[0] for r in cursor.fetchall()]

        for hid in hotels_no_services:
            assign_default_services(cursor, hid)

        for hid in hotels_no_rooms:
            create_default_room_offers(cursor, hid)

        conn.commit()
        return {
            "backfilled_services": len(hotels_no_services),
            "backfilled_rooms": len(hotels_no_rooms),
            "message": "Backfill hoàn tất",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def import_hotels_by_city_to_db(
    city: str,
    max_results: int = 10,
    use_placeholder_for_null: bool = False
):
    if not GEOAPIFY_API_KEY:
        raise Exception("Thiếu GEOAPIFY_API_KEY trong file .env")

    candidate_limit = min(max(max_results * 4, max_results + 20), 200)
    geo_data = search_hotels_from_geoapify(city=city, max_results=candidate_limit)
    hotels = geo_data["hotels"]

    if not hotels:
        return {
            "city": city,
            "total_from_geoapify": 0,
            "inserted": 0,
            "skipped": 0,
            "inserted_hotel_ids": [],
            "message": "Không có khách sạn nào để import"
        }

    conn = get_conn()

    try:
        cursor = conn.cursor()

        city_id = get_or_create_city(
            cursor=cursor,
            city_name=geo_data["city_name"],
            country_name=geo_data["country_name"],
            latitude=geo_data["latitude"],
            longitude=geo_data["longitude"]
        )

        inserted = 0
        skipped = 0
        inserted_hotel_ids = []

        for hotel in hotels:
            if inserted >= max_results:
                break

            hotel_name = normalize_nullable_text(hotel["hotel_name"], use_placeholder_for_null) or "Unnamed hotel"
            address = normalize_nullable_text(hotel["address"], use_placeholder_for_null)
            phone = normalize_phone_text(hotel["phone"], use_placeholder_for_null)
            email = normalize_email_text(hotel["email"], use_placeholder_for_null)
            thumbnail_url = normalize_nullable_text(hotel["thumbnail_url"], use_placeholder_for_null)
            source = normalize_nullable_text(hotel["source"], use_placeholder_for_null) or "Geoapify"

            existing_hotel_id = find_existing_hotel(
                cursor=cursor,
                external_hotel_code=hotel["external_hotel_code"],
                hotel_name=hotel_name,
                address=address,
                city_id=city_id,
                latitude=hotel.get("latitude"),
                longitude=hotel.get("longitude"),
            )

            if existing_hotel_id:
                ensure_hotel_supporting_data(cursor, existing_hotel_id)
                skipped += 1
                continue

            cursor.execute(
                """
                INSERT INTO Hotels (
                    ExternalHotelCode,
                    CityId,
                    HotelName,
                    Description,
                    Address,
                    Latitude,
                    Longitude,
                    StarRating,
                    Phone,
                    Email,
                    ThumbnailUrl,
                    Source
                )
                OUTPUT INSERTED.HotelId
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hotel["external_hotel_code"],
                    city_id,
                    hotel_name,
                    None,
                    address,
                    hotel["latitude"],
                    hotel["longitude"],
                    hotel["star_rating"],
                    phone,
                    email,
                    thumbnail_url,
                    source
                )
            )

            new_row = cursor.fetchone()
            new_hotel_id = new_row.HotelId

            ensure_hotel_supporting_data(cursor, new_hotel_id)

            inserted_hotel_ids.append(new_hotel_id)
            inserted += 1

        conn.commit()

        return {
            "city": geo_data["city_name"],
            "total_from_geoapify": len(hotels),
            "inserted": inserted,
            "skipped": skipped,
            "inserted_hotel_ids": inserted_hotel_ids,
            "message": "Import khách sạn thành công"
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def search_hotels_from_db(filters):
    conn = get_conn()

    try:
        cursor = conn.cursor()

        sql = """
        SELECT
            h.HotelId,
            h.ExternalHotelCode,
            h.HotelName,
            h.Address,
            h.Phone,
            h.Email,
            h.ThumbnailUrl,
            h.Source,
            h.StarRating,
            h.CreatedAt,
            c.CityName,
            c.CountryName,
            ro.MinPrice,
            ro.MaxCapacity,
            ro.TotalAvailableQuantity,
            rv.AverageRating,
            rv.ReviewCount
        FROM Hotels h
        LEFT JOIN Cities c
            ON h.CityId = c.CityId
        LEFT JOIN (
            SELECT
                HotelId,
                MIN(PricePerNight) AS MinPrice,
                MAX(Capacity) AS MaxCapacity,
                SUM(ISNULL(AvailableQuantity, 0)) AS TotalAvailableQuantity
            FROM RoomOffers
            GROUP BY HotelId
        ) ro
            ON h.HotelId = ro.HotelId
        LEFT JOIN (
            SELECT
                HotelId,
                CAST(AVG(CAST(Rating AS FLOAT)) AS DECIMAL(3,2)) AS AverageRating,
                COUNT(*) AS ReviewCount
            FROM Reviews
            WHERE Status = 'Visible'
            GROUP BY HotelId
        ) rv
            ON h.HotelId = rv.HotelId
        WHERE 1 = 1
        """

        params = []

        if filters.city:
            normalized_city = filters.city.strip().lower().replace(" ", "")
            sql += """
                AND REPLACE(LOWER(ISNULL(c.CityName, '') COLLATE Latin1_General_CI_AI), ' ', '') LIKE ?
            """
            params.append(f"%{normalized_city}%")

        if filters.hotel_name:
            normalized_hotel_name = filters.hotel_name.strip().lower()
            sql += """
                AND LOWER(ISNULL(h.HotelName, '') COLLATE Latin1_General_CI_AI) LIKE ?
            """
            params.append(f"%{normalized_hotel_name}%")

        if filters.min_rating is not None:
            sql += " AND h.StarRating IS NOT NULL AND h.StarRating >= ? "
            params.append(filters.min_rating)

        if filters.max_rating is not None:
            sql += " AND h.StarRating IS NOT NULL AND h.StarRating <= ? "
            params.append(filters.max_rating)

        if filters.source:
            sql += " AND LOWER(ISNULL(h.Source, '')) = LOWER(?) "
            params.append(filters.source.strip())

        room_conditions = []
        room_params = []

        if filters.min_price is not None:
            room_conditions.append("r.PricePerNight >= ?")
            room_params.append(filters.min_price)

        if filters.max_price is not None:
            room_conditions.append("r.PricePerNight <= ?")
            room_params.append(filters.max_price)

        if filters.min_capacity is not None:
            room_conditions.append("r.Capacity >= ?")
            room_params.append(filters.min_capacity)

        if filters.min_available_quantity is not None:
            room_conditions.append("ISNULL(r.AvailableQuantity, 0) >= ?")
            room_params.append(filters.min_available_quantity)

        if room_conditions:
            sql += f"""
                AND EXISTS (
                    SELECT 1
                    FROM RoomOffers r
                    WHERE r.HotelId = h.HotelId
                      AND {' AND '.join(room_conditions)}
                )
            """
            params.extend(room_params)

        if filters.sort_by == "price_desc":
            sql += " ORDER BY CASE WHEN ro.MinPrice IS NULL THEN 1 ELSE 0 END, ro.MinPrice DESC, h.HotelId DESC "
        elif filters.sort_by == "rating_desc":
            sql += " ORDER BY CASE WHEN h.StarRating IS NULL THEN 1 ELSE 0 END, h.StarRating DESC, h.HotelId DESC "
        elif filters.sort_by == "newest":
            sql += " ORDER BY h.CreatedAt DESC, h.HotelId DESC "
        else:
            sql += " ORDER BY CASE WHEN ro.MinPrice IS NULL THEN 1 ELSE 0 END, ro.MinPrice ASC, h.HotelId DESC "

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "hotel_id": row.HotelId,
                "external_hotel_code": row.ExternalHotelCode,
                "hotel_name": row.HotelName,
                "city": row.CityName if row.CityName else "Đang cập nhật",
                "country": row.CountryName if row.CountryName else "Đang cập nhật",
                "address": row.Address if row.Address else "Đang cập nhật",
                "phone": row.Phone if row.Phone else "Đang cập nhật",
                "email": row.Email if row.Email else "Đang cập nhật",
                "thumbnail_url": row.ThumbnailUrl if row.ThumbnailUrl else "Đang cập nhật",
                "source": row.Source if row.Source else "Đang cập nhật",
                "star_rating": float(row.StarRating) if row.StarRating is not None else None,
                "min_price": float(row.MinPrice) if row.MinPrice is not None else None,
                "max_capacity": int(row.MaxCapacity) if row.MaxCapacity is not None else 0,
                "total_available_quantity": int(row.TotalAvailableQuantity) if row.TotalAvailableQuantity is not None else 0,
                "average_rating": float(row.AverageRating) if row.AverageRating is not None else 0,
                "review_count": int(row.ReviewCount) if row.ReviewCount is not None else 0,
                "created_at": str(row.CreatedAt) if row.CreatedAt is not None else None
            })

        return {
            "total": len(results),
            "filters": {
                "city": filters.city,
                "hotel_name": filters.hotel_name,
                "min_price": filters.min_price,
                "max_price": filters.max_price,
                "min_rating": filters.min_rating,
                "max_rating": filters.max_rating,
                "min_capacity": filters.min_capacity,
                "min_available_quantity": filters.min_available_quantity,
                "source": filters.source,
                "sort_by": filters.sort_by
            },
            "items": results
        }

    finally:
        conn.close()

def delete_hotel_by_id(hotel_id: int):
    conn = get_conn()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT TOP 1 HotelId, HotelName
            FROM Hotels
            WHERE HotelId = ?
            """,
            (hotel_id,)
        )
        hotel = cursor.fetchone()

        if not hotel:
            raise HTTPException(status_code=404, detail="Không tìm thấy khách sạn")

        cursor.execute(
            """
            SELECT COUNT(*) AS TotalBookings
            FROM Bookings
            WHERE HotelId = ?
            """,
            (hotel_id,)
        )
        booking_row = cursor.fetchone()
        total_bookings = int(booking_row.TotalBookings) if booking_row else 0

        if total_bookings > 0:
            raise HTTPException(
                status_code=400,
                detail="Không thể xóa khách sạn vì đã phát sinh booking"
            )

        cursor.execute("SELECT COUNT(*) AS Total FROM FavoriteHotels WHERE HotelId = ?", (hotel_id,))
        favorite_count = int(cursor.fetchone().Total)

        cursor.execute("SELECT COUNT(*) AS Total FROM HotelImages WHERE HotelId = ?", (hotel_id,))
        image_count = int(cursor.fetchone().Total)

        cursor.execute("SELECT COUNT(*) AS Total FROM HotelServices WHERE HotelId = ?", (hotel_id,))
        hotel_service_count = int(cursor.fetchone().Total)

        cursor.execute("SELECT COUNT(*) AS Total FROM RoomOffers WHERE HotelId = ?", (hotel_id,))
        room_offer_count = int(cursor.fetchone().Total)

        cursor.execute("SELECT COUNT(*) AS Total FROM Reviews WHERE HotelId = ?", (hotel_id,))
        review_count = int(cursor.fetchone().Total)

        cursor.execute("DELETE FROM FavoriteHotels WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM HotelImages WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM HotelServices WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM Reviews WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM RoomOffers WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM Hotels WHERE HotelId = ?", (hotel_id,))

        conn.commit()

        return {
            "message": "Xóa khách sạn thành công",
            "deleted_hotel_id": hotel_id,
            "hotel_name": hotel.HotelName,
            "deleted_related_data": {
                "favorite_hotels": favorite_count,
                "hotel_images": image_count,
                "hotel_services": hotel_service_count,
                "reviews": review_count,
                "room_offers": room_offer_count
            }
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
