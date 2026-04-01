import os
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

from core.database import get_conn

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
            "source": "Geoapify"
        })

    return {
        "city_name": geo["city_name"],
        "country_name": geo["country_name"],
        "latitude": geo["lat"],
        "longitude": geo["lon"],
        "hotels": hotels
    }


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
        return row.CityId

    cursor.execute(
        """
        INSERT INTO Cities (CityName, CountryName, Latitude, Longitude)
        OUTPUT INSERTED.CityId
        VALUES (?, ?, ?, ?)
        """,
        (city_name, country_name, latitude, longitude)
    )
    new_row = cursor.fetchone()
    return new_row.CityId


def find_existing_hotel(
    cursor,
    external_hotel_code: Optional[str],
    hotel_name: str,
    address: Optional[str],
    city_id: int
):
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
    return row.HotelId if row else None


def create_default_room_offers(cursor, hotel_id: int):
    demo_offers = [
        {
            "room_type": "Phòng Standard",
            "description": "Phòng demo để hiển thị UI. Staff có thể chỉnh sửa lại sau.",
            "capacity": 2,
            "price_per_night": 850000,
            "currency": "VND",
            "available_quantity": 5,
            "cancellation_policy": "Giá demo cho đồ án, staff có thể cập nhật chính sách hủy sau.",
            "amenities": "1 giường đôi, wifi, máy lạnh"
        },
        {
            "room_type": "Phòng Deluxe",
            "description": "Phòng rộng hơn, phù hợp để demo card giá/phòng ở trang detail.",
            "capacity": 4,
            "price_per_night": 1250000,
            "currency": "VND",
            "available_quantity": 3,
            "cancellation_policy": "Giá demo cho mục đích học tập, staff có thể cập nhật sau.",
            "amenities": "2 giường, wifi, máy lạnh, view đẹp"
        }
    ]

    for offer in demo_offers:
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
                offer["room_type"],
                offer["description"],
                offer["capacity"],
                offer["price_per_night"],
                offer["currency"],
                offer["available_quantity"],
                None,
                None,
                offer["cancellation_policy"],
                offer["amenities"]
            )
        )


def import_hotels_by_city_to_db(
    city: str,
    max_results: int = 10,
    use_placeholder_for_null: bool = False
):
    if not GEOAPIFY_API_KEY:
        raise Exception("Thiếu GEOAPIFY_API_KEY trong file .env")

    geo_data = search_hotels_from_geoapify(city=city, max_results=max_results)
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
            hotel_name = normalize_nullable_text(hotel["hotel_name"], use_placeholder_for_null) or "Unnamed hotel"
            address = normalize_nullable_text(hotel["address"], use_placeholder_for_null)
            phone = normalize_nullable_text(hotel["phone"], use_placeholder_for_null)
            email = normalize_nullable_text(hotel["email"], use_placeholder_for_null)
            thumbnail_url = normalize_nullable_text(hotel["thumbnail_url"], use_placeholder_for_null)
            source = normalize_nullable_text(hotel["source"], use_placeholder_for_null) or "Geoapify"

            existing_hotel_id = find_existing_hotel(
                cursor=cursor,
                external_hotel_code=hotel["external_hotel_code"],
                hotel_name=hotel_name,
                address=address,
                city_id=city_id
            )

            if existing_hotel_id:
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
                    None,
                    phone,
                    email,
                    thumbnail_url,
                    source
                )
            )

            new_row = cursor.fetchone()
            new_hotel_id = new_row.HotelId

            create_default_room_offers(cursor, new_hotel_id)

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
            sql += " AND rv.AverageRating IS NOT NULL AND rv.AverageRating >= ? "
            params.append(filters.min_rating)

        if filters.min_review_count is not None:
            sql += " AND rv.ReviewCount IS NOT NULL AND rv.ReviewCount >= ? "
            params.append(filters.min_review_count)

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
            sql += " ORDER BY CASE WHEN rv.AverageRating IS NULL THEN 1 ELSE 0 END, rv.AverageRating DESC, rv.ReviewCount DESC, h.HotelId DESC "
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
                "min_review_count": filters.min_review_count,
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

        # 1. Kiểm tra hotel có tồn tại không
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

        # 2. Không cho xóa nếu đã có booking
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

        # 3. Đếm trước số bản ghi sẽ xóa để trả response đẹp hơn
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

        # 4. Xóa dữ liệu con
        # Reviews thường không có nếu không có booking, nhưng cứ xóa để an toàn nếu có dữ liệu test thủ công
        cursor.execute("DELETE FROM FavoriteHotels WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM HotelImages WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM HotelServices WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM Reviews WHERE HotelId = ?", (hotel_id,))
        cursor.execute("DELETE FROM RoomOffers WHERE HotelId = ?", (hotel_id,))

        # 5. Xóa hotel
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