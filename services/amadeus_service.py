import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Tương thích ngược: nếu bạn vẫn đang dùng tên biến AMADEUS_API_KEY
# thì file này vẫn chạy được với Geoapify.
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY") or os.getenv("AMADEUS_API_KEY")
GEOAPIFY_BASE_URL = (
    os.getenv("GEOAPIFY_BASE_URL")
    or os.getenv("AMADEUS_BASE_URL")
    or "https://api.geoapify.com"
)

DEFAULT_IMAGES = [
    {
        "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=1200&auto=format&fit=crop",
        "caption": "Hotel",
    },
    {
        "url": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?q=80&w=1200&auto=format&fit=crop",
        "caption": "Room",
    },
    {
        "url": "https://images.unsplash.com/photo-1445019980597-93fa8acb246c?q=80&w=1200&auto=format&fit=crop",
        "caption": "View",
    },
    {
        "url": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1200&auto=format&fit=crop",
        "caption": "Interior",
    },
    {
        "url": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?q=80&w=1200&auto=format&fit=crop",
        "caption": "Lobby",
    },
]

CITY_CODE_ALIASES = {
    "BKK": "Bangkok",
    "PAR": "Paris",
    "SGN": "Ho Chi Minh City",
    "HAN": "Hanoi",
    "DAD": "Da Nang",
    "NHA": "Nha Trang",
    "DLI": "Da Lat",
    "HUI": "Hue",
    "SIN": "Singapore",
    "TYO": "Tokyo",
    "OSA": "Osaka",
    "ICN": "Seoul",
    "HKG": "Hong Kong",
    "LON": "London",
    "NYC": "New York",
    "LAX": "Los Angeles",
    "SFO": "San Francisco",
    "BJS": "Beijing",
    "SHA": "Shanghai",
    "KUL": "Kuala Lumpur",
}


def _check_env() -> None:
    if not GEOAPIFY_API_KEY:
        raise ValueError(
            "Thiếu GEOAPIFY_API_KEY trong file .env "
            "(hoặc tạm thời có thể dùng AMADEUS_API_KEY để tương thích)."
        )


def _geoapify_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    _check_env()
    final_params = dict(params or {})
    final_params["apiKey"] = GEOAPIFY_API_KEY

    with httpx.Client(base_url=GEOAPIFY_BASE_URL, timeout=25.0) as client:
        response = client.get(path, params=final_params)
        response.raise_for_status()
        return response.json()


def _normalize_city_input(city_code: str | None = None, city: str | None = None) -> str:
    raw = (city or city_code or "").strip()
    if not raw:
        raise ValueError("Thiếu city hoặc city_code")

    upper = raw.upper()
    return CITY_CODE_ALIASES.get(upper, raw)


def _geocode_city(city_text: str) -> dict[str, Any]:
    payload = _geoapify_get(
        "/v1/geocode/search",
        {
            "text": city_text,
            "type": "city",
            "format": "json",
            "limit": 1,
            "lang": "vi",
        },
    )

    results = payload.get("results") or []
    if not results:
        raise ValueError(f"Không tìm thấy thành phố: {city_text}")

    return results[0]


def _build_city_filter(geo: dict[str, Any]) -> tuple[str, str]:
    lon = geo.get("lon")
    lat = geo.get("lat")
    bbox = geo.get("bbox") or {}

    if bbox:
        lon1 = bbox.get("lon1")
        lat1 = bbox.get("lat1")
        lon2 = bbox.get("lon2")
        lat2 = bbox.get("lat2")
        if None not in (lon1, lat1, lon2, lat2):
            return f"rect:{lon1},{lat1},{lon2},{lat2}", f"proximity:{lon},{lat}"

    if None in (lon, lat):
        raise ValueError("Không lấy được tọa độ thành phố từ Geoapify")

    return f"circle:{lon},{lat},12000", f"proximity:{lon},{lat}"


def _category_to_country_code(props: dict[str, Any]) -> str | None:
    country_code = props.get("country_code")
    if country_code:
        return str(country_code).upper()
    return None


def _hotel_list_item_from_feature(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties") or {}

    return {
        "hotel_id": props.get("place_id"),
        "name": props.get("name") or props.get("address_line1") or "Unnamed hotel",
        "address": props.get("formatted") or props.get("address_line2") or "",
        "city_code": None,
        "country_code": _category_to_country_code(props),
        "latitude": props.get("lat"),
        "longitude": props.get("lon"),
        "thumbnail": None,
    }


def search_hotels_by_city(
    city_code: str | None = None,
    max_results: int = 12,
    city: str | None = None,
) -> list[dict[str, Any]]:
    city_text = _normalize_city_input(city_code=city_code, city=city)
    geo = _geocode_city(city_text)
    filter_value, bias_value = _build_city_filter(geo)

    payload = _geoapify_get(
        "/v2/places",
        {
            "categories": "accommodation.hotel",
            "filter": filter_value,
            "bias": bias_value,
            "limit": max_results,
            "lang": "vi",
        },
    )

    features = payload.get("features") or []
    return [_hotel_list_item_from_feature(item) for item in features[:max_results]]


def _extract_detail_feature(payload: dict[str, Any]) -> dict[str, Any]:
    features = payload.get("features") or []
    for feature in features:
        props = feature.get("properties") or {}
        if props.get("feature_type") == "details":
            return feature
    return features[0] if features else {}


def _bool_amenity(value: Any, label: str) -> str | None:
    return label if value is True else None


def _extract_amenities(props: dict[str, Any]) -> list[str]:
    amenities = [
        _bool_amenity(props.get("internet_access"), "Wi‑Fi"),
        _bool_amenity(props.get("air_conditioning"), "Điều hòa"),
        _bool_amenity(props.get("swimming_pool"), "Hồ bơi"),
        _bool_amenity(props.get("wheelchair"), "Hỗ trợ xe lăn"),
        _bool_amenity(props.get("toilets"), "Nhà vệ sinh"),
        _bool_amenity(props.get("dogs"), "Cho phép thú cưng"),
    ]

    accommodation = props.get("accommodation") or {}
    stars = accommodation.get("stars")
    rooms = accommodation.get("rooms")
    beds = accommodation.get("beds")
    reservation = accommodation.get("reservation")

    if stars:
        amenities.append(f"{stars} sao")
    if rooms:
        amenities.append(f"{rooms} phòng")
    if beds:
        amenities.append(f"{beds} giường")
    if reservation:
        amenities.append(f"Reservation: {reservation}")

    categories = props.get("categories") or []
    if isinstance(categories, list):
        for cat in categories:
            if cat.startswith("accommodation.") and cat != "accommodation.hotel":
                amenities.append(cat.replace("accommodation.", "").replace("_", " ").title())

    seen = set()
    result = []
    for item in amenities:
        if item and item not in seen:
            seen.add(item)
            result.append(item)

    return result[:12]


def _make_description(props: dict[str, Any]) -> str:
    lines = []
    categories = props.get("categories") or []
    accommodation = props.get("accommodation") or {}

    if props.get("formatted"):
        lines.append(f"Địa chỉ: {props['formatted']}.")
    if accommodation.get("stars"):
        lines.append(f"Hạng sao tham chiếu: {accommodation['stars']} sao.")
    if accommodation.get("rooms"):
        lines.append(f"Số phòng tham chiếu: {accommodation['rooms']}.")
    if props.get("opening_hours"):
        lines.append(f"Giờ hoạt động: {props['opening_hours']}.")
    if categories:
        pretty = ", ".join(str(x) for x in categories[:4])
        lines.append(f"Nhóm dữ liệu: {pretty}.")

    if not lines:
        return (
            "Khách sạn này hiện chưa có nhiều mô tả chi tiết từ Geoapify. "
            "Bạn có thể lưu thêm description, ảnh, giá phòng và review mock trong SQL nội bộ."
        )

    return " ".join(lines)


def _mock_offers(check_in: str, adults: int) -> list[dict[str, Any]]:
    return [
        {
            "offer_id": "demo-standard",
            "room_type": "Phòng Standard",
            "description": "Phòng demo để hiển thị UI. Geoapify không cung cấp giá phòng live như booking engine.",
            "beds": 1,
            "bed_type": "Double",
            "capacity": max(2, adults),
            "price_total": 850000,
            "price_base": 750000,
            "currency": "VND",
            "check_in_date": check_in,
            "check_out_date": None,
            "cancellation_policy": "Giá demo cho đồ án, chưa có chính sách hủy thật từ API.",
            "payment_type": "Pay at hotel",
        },
        {
            "offer_id": "demo-deluxe",
            "room_type": "Phòng Deluxe",
            "description": "Phòng rộng hơn, phù hợp để demo card giá/phòng ở trang detail.",
            "beds": 2,
            "bed_type": "Twin",
            "capacity": max(2, adults),
            "price_total": 1250000,
            "price_base": 1100000,
            "currency": "VND",
            "check_in_date": check_in,
            "check_out_date": None,
            "cancellation_policy": "Giá demo cho mục đích học tập.",
            "payment_type": "Pay now",
        },
    ]


def get_hotel_detail_payload(hotel_id: str, check_in: str, adults: int = 2) -> dict[str, Any]:
    payload = _geoapify_get(
        "/v2/place-details",
        {
            "id": hotel_id,
            "features": "details",
            "lang": "vi",
        },
    )

    feature = _extract_detail_feature(payload)
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or [None, None]

    lon = props.get("lon") if props.get("lon") is not None else coordinates[0]
    lat = props.get("lat") if props.get("lat") is not None else coordinates[1]

    offers = _mock_offers(check_in=check_in, adults=adults)
    numeric_prices = [float(x["price_total"]) for x in offers if x.get("price_total")]
    price_from = min(numeric_prices) if numeric_prices else None

    stars = None
    accommodation = props.get("accommodation") or {}
    if accommodation.get("stars"):
        try:
            stars = float(str(accommodation.get("stars")).replace("S", ""))
        except ValueError:
            stars = None

    return {
        "hotel_id": hotel_id,
        "name": props.get("name") or props.get("address_line1") or "Unknown hotel",
        "chain_code": None,
        "address": props.get("formatted") or props.get("address_line2") or "",
        "latitude": lat,
        "longitude": lon,
        "description": _make_description(props),
        "amenities": _extract_amenities(props),
        "images": DEFAULT_IMAGES,
        "offers": offers,
        "price_from": price_from,
        "currency": "VND",
        "check_in": check_in,
        "adults": adults,
        "rating": {
            "overall": stars,
            "reviews_count": None,
            "sentiments": {},
        },
    }
