import os
import requests
from dotenv import load_dotenv
from core.database import get_conn
load_dotenv()

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
GEOAPIFY_BASE_URL = os.getenv("GEOAPIFY_BASE_URL", "https://api.geoapify.com")


def geocode_city(city: str):
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
        props = item.get("properties", {})

        hotels.append({
            "external_hotel_code": str(props.get("place_id") or props.get("datasource", {}).get("raw", {}).get("osm_id") or ""),
            "hotel_name": props.get("name") or "Unnamed hotel",
            "address": props.get("formatted") or props.get("address_line2") or "",
            "latitude": props.get("lat"),
            "longitude": props.get("lon"),
            "phone": props.get("contact", {}).get("phone") if isinstance(props.get("contact"), dict) else None,
            "email": props.get("contact", {}).get("email") if isinstance(props.get("contact"), dict) else None,
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


def find_existing_hotel(cursor, external_hotel_code: str, hotel_name: str, address: str, city_id: int):
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

    return None


def import_hotels_by_city_to_db(city: str, max_results: int = 10):
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
            existing_hotel_id = find_existing_hotel(
                cursor=cursor,
                external_hotel_code=hotel["external_hotel_code"],
                hotel_name=hotel["hotel_name"],
                address=hotel["address"],
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
                    hotel["external_hotel_code"] or None,
                    city_id,
                    hotel["hotel_name"],
                    None,
                    hotel["address"],
                    hotel["latitude"],
                    hotel["longitude"],
                    None,
                    hotel["phone"],
                    hotel["email"],
                    None,
                    hotel["source"]
                )
            )

            new_row = cursor.fetchone()
            inserted_hotel_ids.append(new_row.HotelId)
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

    except:
        conn.rollback()
        raise
    finally:
        conn.close()