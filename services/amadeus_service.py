import os
from typing import Any
from datetime import datetime, timedelta
import httpx
from dotenv import load_dotenv

load_dotenv()

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY") or os.getenv("AMADEUS_API_KEY")
GEOAPIFY_BASE_URL = (
    os.getenv("GEOAPIFY_BASE_URL")
    or os.getenv("AMADEUS_BASE_URL")
    or "https://api.geoapify.com"
)

# ── OpenWeatherMap ─────────────────────────────────────────────────────────────
OWM_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY") or os.getenv("OPENWEATHER_API_KEY")
OWM_BASE_URL = "https://api.openweathermap.org"

# ── Pool ảnh khách sạn từ Unsplash (public, không cần API key) ────────────────
# Mỗi ảnh được tag theo loại để tạo gallery đa dạng cho detail page.
# Dùng seed từ hotel_id để mỗi khách sạn có bộ ảnh riêng, nhất quán giữa các lần load.

_HOTEL_PHOTO_POOL: list[tuple[str, str]] = [
    # ── Exterior / Pool ──────────────────────────────────────────────────────
    ("1566073771259-6a8506099945", "Hồ bơi ngoài trời"),
    ("1520250497591-112f2f40a3f4", "Khu nghỉ dưỡng"),
    ("1571896349842-33c89424de2d", "Mặt tiền khách sạn"),
    ("1542314831-068cd1dbfeeb",   "Toàn cảnh resort"),
    ("1584132967334-10e028bd69f7", "Hồ bơi vô cực"),
    ("1551882547-ff40c63fe5fa",   "Khu vực ngoài trời"),
    ("1582719508461-905c673771fd", "Sảnh đón"),
    ("1455587734955-f54d5b57e8b0", "Không gian xanh"),
    # ── Room / Interior ──────────────────────────────────────────────────────
    ("1522708323590-d24dbb6b0267", "Phòng nghỉ"),
    ("1618773928121-c32242e63f39", "Phòng Deluxe"),
    ("1631049307264-da0ec9d70304", "Phòng Suite"),
    ("1505693416388-ac5ce068fe85", "Nội thất"),
    ("1540518614846-7eded433c457", "Phòng ngủ"),
    ("1561501900-3701fa6a0864",   "Không gian phòng"),
    ("1587985064135-0366536eab42", "View từ phòng"),
    ("1611892440504-42a792e24d32", "Phòng cao cấp"),
    # ── Dining / Lobby ───────────────────────────────────────────────────────
    ("1445019980597-93fa8acb246c", "Nhà hàng"),
    ("1414235077428-338989a2e8c0", "Ẩm thực"),
    ("1559329007-0c8cfd9d3fca",   "Quầy bar"),
    ("1486325212027-8081e485255e", "Sảnh chính"),
    # ── Spa / Gym ────────────────────────────────────────────────────────────
    ("1544161515-4ab6ce6db874",   "Spa & Wellness"),
    ("1540555700478-4be290a57523", "Trung tâm thể thao"),
    # ── View / Location ──────────────────────────────────────────────────────
    ("1512917774080-9991f1c4c750", "Cảnh quan"),
    ("1499793983690-e29da59ef1c2", "Tầm nhìn"),
    ("1506973035872-a4ec16b8e8d9", "Hoàng hôn"),
]


def _unsplash_url(photo_id: str, w: int = 900, h: int = 600) -> str:
    """Tạo URL Unsplash CDN trực tiếp theo photo_id — không cần API key."""
    return (
        f"https://images.unsplash.com/photo-{photo_id}"
        f"?q=80&w={w}&h={h}&auto=format&fit=crop"
    )


# ── Helpers tính index từ hotel_id (seed-based, nhất quán) ───────────────────

def _pool_indexes_for_hotel(hotel_id: str) -> tuple[int, list[int]]:
    """Trả về (thumbnail_index, gallery_indexes[5]) từ hotel_id."""
    seed = sum(ord(c) for c in str(hotel_id))
    n = len(_HOTEL_PHOTO_POOL)
    thumb_idx = seed % n
    gallery_idxs = [(seed + i * 3) % n for i in range(5)]
    return thumb_idx, gallery_idxs


def _hotel_thumbnail_fallback(hotel_id: str) -> str:
    """Thumbnail tính từ pool — dùng khi DB chưa có ảnh."""
    thumb_idx, _ = _pool_indexes_for_hotel(hotel_id)
    photo_id, _ = _HOTEL_PHOTO_POOL[thumb_idx]
    return _unsplash_url(photo_id, w=480, h=320)


def _hotel_gallery_fallback(hotel_id: str) -> list[dict[str, str]]:
    """Gallery 5 ảnh tính từ pool — dùng khi DB chưa có ảnh."""
    _, gallery_idxs = _pool_indexes_for_hotel(hotel_id)
    return [
        {
            "url":     _unsplash_url(_HOTEL_PHOTO_POOL[i][0], w=1200, h=800),
            "caption": _HOTEL_PHOTO_POOL[i][1],
        }
        for i in gallery_idxs
    ]


def _hotel_thumbnail(hotel_id: str) -> str:
    """
    Thumbnail cho hotel: ưu tiên DB → fallback pool.
    Nếu chưa có trong DB, upsert để lần sau đọc từ DB.
    """
    try:
        from Db import query_one
        row = query_one(
            "SELECT TOP 1 hi.ImageUrl FROM HotelImages hi "
            "JOIN Hotels h ON h.HotelId = hi.HotelId "
            "WHERE h.ExternalHotelCode = ? AND hi.DisplayOrder = 0",
            (hotel_id,),
        )
        if row and row.get("ImageUrl"):
            return row["ImageUrl"]
    except Exception:
        pass  # DB chưa sẵn sàng — dùng fallback

    # Chưa có → upsert (fire-and-forget)
    _upsert_hotel_images_to_db(hotel_id)
    return _hotel_thumbnail_fallback(hotel_id)


def _hotel_gallery(hotel_id: str) -> list[dict[str, str]]:
    """
    Gallery 5 ảnh cho detail page: ưu tiên DB → fallback pool.
    """
    try:
        from Db import query_all
        rows = query_all(
            "SELECT hi.ImageUrl, hi.Caption FROM HotelImages hi "
            "JOIN Hotels h ON h.HotelId = hi.HotelId "
            "WHERE h.ExternalHotelCode = ? AND hi.DisplayOrder >= 1 "
            "ORDER BY hi.DisplayOrder",
            (hotel_id,),
        )
        if rows:
            return [{"url": r["ImageUrl"], "caption": r["Caption"] or ""} for r in rows]
    except Exception:
        pass

    return _hotel_gallery_fallback(hotel_id)


def _upsert_hotel_images_to_db(hotel_id: str) -> None:
    """
    Lưu ảnh của hotel vào DB (HotelImages) nếu chưa có.
    Gọi sau khi Hotels đã có record với ExternalHotelCode = hotel_id.
    Nếu Hotels chưa có thì bỏ qua — sẽ được retry lần sau.
    """
    try:
        from Db import query_one, get_connection

        hotel_row = query_one(
            "SELECT HotelId FROM Hotels WHERE ExternalHotelCode = ?",
            (hotel_id,),
        )
        if not hotel_row:
            return  # Hotels chưa có record này

        db_hotel_id = hotel_row["HotelId"]

        existing = query_one(
            "SELECT COUNT(*) AS cnt FROM HotelImages WHERE HotelId = ?",
            (db_hotel_id,),
        )
        if existing and existing.get("cnt", 0) > 0:
            return  # Đã có ảnh, không ghi đè

        thumb_idx, gallery_idxs = _pool_indexes_for_hotel(hotel_id)
        n = len(_HOTEL_PHOTO_POOL)

        with get_connection() as conn:
            cursor = conn.cursor()

            # Thumbnail (DisplayOrder = 0)
            t_photo_id, t_caption = _HOTEL_PHOTO_POOL[thumb_idx % n]
            cursor.execute(
                "INSERT INTO HotelImages (HotelId, ImageUrl, Caption, DisplayOrder) "
                "VALUES (?, ?, ?, 0)",
                (db_hotel_id, _unsplash_url(t_photo_id, w=480, h=320), t_caption),
            )

            # Gallery (DisplayOrder 1-5)
            for order, idx in enumerate(gallery_idxs, start=1):
                g_photo_id, g_caption = _HOTEL_PHOTO_POOL[idx % n]
                cursor.execute(
                    "INSERT INTO HotelImages (HotelId, ImageUrl, Caption, DisplayOrder) "
                    "VALUES (?, ?, ?, ?)",
                    (db_hotel_id, _unsplash_url(g_photo_id, w=1200, h=800), g_caption, order),
                )

            conn.commit()

    except Exception as exc:
        import traceback as _tb
        print(f"[warn] _upsert_hotel_images_to_db({hotel_id}): {exc}")
        _tb.print_exc()

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


# ══════════════════════════════════════════════════════════════════════════════
#  GEOAPIFY helpers
# ══════════════════════════════════════════════════════════════════════════════

def _check_env() -> None:
    if not GEOAPIFY_API_KEY:
        raise ValueError("Thiếu GEOAPIFY_API_KEY trong file .env")


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
        {"text": city_text, "type": "city", "format": "json", "limit": 1, "lang": "vi"},
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
        lon1, lat1 = bbox.get("lon1"), bbox.get("lat1")
        lon2, lat2 = bbox.get("lon2"), bbox.get("lat2")
        if None not in (lon1, lat1, lon2, lat2):
            return f"rect:{lon1},{lat1},{lon2},{lat2}", f"proximity:{lon},{lat}"
    if None in (lon, lat):
        raise ValueError("Không lấy được tọa độ thành phố từ Geoapify")
    return f"circle:{lon},{lat},12000", f"proximity:{lon},{lat}"


def _category_to_country_code(props: dict[str, Any]) -> str | None:
    country_code = props.get("country_code")
    return str(country_code).upper() if country_code else None


def _mock_hotel_meta(hotel_id: str) -> dict[str, Any]:
    seed = sum(ord(c) for c in str(hotel_id))

    stars_options = [3, 4, 5, 4, 3, 5]
    price_options = [450000, 550000, 750000, 890000, 1100000, 1300000, 1500000]
    amenity_options = [
        ["Wi-Fi", "Điều hòa", "Bãi đỗ xe"],
        ["Wi-Fi", "Hồ bơi", "Phòng gym"],
        ["Wi-Fi", "Điều hòa", "Nhà hàng", "Spa"],
        ["Wi-Fi", "Bãi đỗ xe", "Điều hòa"],
        ["Wi-Fi", "Hồ bơi", "Nhà hàng"],
        ["Wi-Fi", "Điều hòa"],
    ]

    stars = stars_options[seed % len(stars_options)]
    price = price_options[seed % len(price_options)]
    amenities = amenity_options[seed % len(amenity_options)]

    return {
        "stars": stars,
        "rating_overall": float(stars),
        "price_from": price,
        "amenities": amenities,
    }

def _hotel_list_item_from_feature(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties") or {}
    hotel_id = props.get("place_id")
    meta = _mock_hotel_meta(hotel_id)

    return {
        "hotel_id": hotel_id,
        "name": props.get("name") or props.get("address_line1") or "Unnamed hotel",
        "address": props.get("formatted") or props.get("address_line2") or "",
        "city_code": None,
        "country_code": _category_to_country_code(props),
        "latitude": props.get("lat"),
        "longitude": props.get("lon"),
        "thumbnail": _hotel_thumbnail(hotel_id),
        "stars": meta["stars"],
        "price_from": meta["price_from"],
        "rating_overall": meta["rating_overall"],
        "amenities_preview": meta["amenities"],
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


# ══════════════════════════════════════════════════════════════════════════════
#  OPENWEATHERMAP helpers
# ══════════════════════════════════════════════════════════════════════════════

def _owm_icon_url(icon_code: str) -> str:
    return f"https://openweathermap.org/img/wn/{icon_code}@2x.png"


def get_weather_by_city(
    city: str | None = None,
    city_code: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    lang: str = "vi",
) -> dict[str, Any]:
    """
    Gọi OpenWeatherMap Current Weather API.
    Ưu tiên: lat/lon > city/city_code (text).
    Thêm OPENWEATHERMAP_API_KEY vào .env
    """
    if not OWM_API_KEY:
        raise ValueError(
            "Thiếu OPENWEATHERMAP_API_KEY trong .env. "
            "Đăng ký miễn phí tại https://openweathermap.org/api"
        )

    params: dict[str, Any] = {
        "appid": OWM_API_KEY,
        "units": "metric",   # Celsius
        "lang": lang,
    }

    if lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon
    else:
        # Resolve city_code alias nếu cần
        raw = city or city_code or ""
        city_text = _normalize_city_input(city=raw) if raw else ""
        if not city_text:
            raise ValueError("Cần truyền city, city_code hoặc lat/lon")
        params["q"] = city_text

    with httpx.Client(base_url=OWM_BASE_URL, timeout=10.0) as client:
        res = client.get("/data/2.5/weather", params=params)
        if res.status_code == 401:
            raise ValueError("API key OpenWeatherMap không hợp lệ hoặc chưa kích hoạt.")
        if res.status_code == 404:
            raise ValueError("Không tìm thấy thành phố trên OpenWeatherMap.")
        res.raise_for_status()
        data = res.json()

    weather = data.get("weather", [{}])[0]
    main = data.get("main", {})
    wind = data.get("wind", {})
    sys = data.get("sys", {})

    return {
        "city": data.get("name", ""),
        "country": sys.get("country", ""),
        "temp": round(main.get("temp", 0)),
        "feels_like": round(main.get("feels_like", 0)),
        "temp_min": round(main.get("temp_min", 0)),
        "temp_max": round(main.get("temp_max", 0)),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "wind_speed": round(wind.get("speed", 0) * 3.6),   # m/s → km/h
        "wind_deg": wind.get("deg"),
        "description": weather.get("description", ""),
        "icon_code": weather.get("icon", ""),
        "icon_url": _owm_icon_url(weather.get("icon", "01d")),
        "visibility": data.get("visibility"),
        "clouds": data.get("clouds", {}).get("all"),
        "latitude": data.get("coord", {}).get("lat"),
        "longitude": data.get("coord", {}).get("lon"),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  HOTEL DETAIL helpers (không đổi)
# ══════════════════════════════════════════════════════════════════════════════

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
    seen: set[str] = set()
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
            "description": "Phòng demo để hiển thị UI.",
            "beds": 1,
            "bed_type": "Double",
            "capacity": max(2, adults),
            "price_total": 850000,
            "price_base": 750000,
            "currency": "VND",
            "check_in_date": check_in,
            "check_out_date": None,
            "cancellation_policy": "Miễn phí hủy trước 24h.",
            "payment_type": "Pay at hotel",
        },
        {
            "offer_id": "demo-deluxe",
            "room_type": "Phòng Deluxe",
            "description": "Phòng rộng hơn, view đẹp.",
            "beds": 2,
            "bed_type": "Twin",
            "capacity": max(2, adults),
            "price_total": 1250000,
            "price_base": 1100000,
            "currency": "VND",
            "check_in_date": check_in,
            "check_out_date": None,
            "cancellation_policy": "Miễn phí hủy trước 48h.",
            "payment_type": "Pay now",
        },
    ]

def _pick_midday_item(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}

    def score(x: dict[str, Any]) -> int:
        dt_txt = x.get("dt_txt", "")
        try:
            hour = int(dt_txt[11:13])
            return abs(hour - 12)
        except Exception:
            return 999

    return sorted(items, key=score)[0]


def _map_forecast_item(item: dict[str, Any]) -> dict[str, Any]:
    weather = (item.get("weather") or [{}])[0]
    main = item.get("main") or {}
    wind = item.get("wind") or {}

    return {
        "date": item.get("dt_txt", "")[:10],
        "temp": round(main.get("temp", 0)),
        "feels_like": round(main.get("feels_like", 0)),
        "temp_min": round(main.get("temp_min", 0)),
        "temp_max": round(main.get("temp_max", 0)),
        "humidity": main.get("humidity"),
        "description": weather.get("description", ""),
        "icon_code": weather.get("icon", ""),
        "icon_url": _owm_icon_url(weather.get("icon", "01d")),
        "wind_speed": round(wind.get("speed", 0) * 3.6),
        "clouds": (item.get("clouds") or {}).get("all"),
    }


def get_weather_forecast_3days(
    city: str | None = None,
    city_code: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    check_in: str | None = None,
    lang: str = "vi",
) -> dict[str, Any]:
    if not OWM_API_KEY:
        raise ValueError("Thiếu OPENWEATHERMAP_API_KEY hoặc OPENWEATHER_API_KEY trong .env")

    params: dict[str, Any] = {
        "appid": OWM_API_KEY,
        "units": "metric",
        "lang": lang,
    }

    if lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon
    else:
        city_text = _normalize_city_input(city_code=city_code, city=city)
        params["q"] = city_text

    with httpx.Client(base_url=OWM_BASE_URL, timeout=15.0) as client:
        res = client.get("/data/2.5/forecast", params=params)

        if res.status_code == 401:
            raise ValueError("API key OpenWeatherMap không hợp lệ hoặc chưa kích hoạt.")
        if res.status_code == 404:
            raise ValueError("Không tìm thấy thành phố trên OpenWeatherMap.")

        res.raise_for_status()
        data = res.json()

    city_info = data.get("city") or {}
    all_items = data.get("list") or []

    if not all_items:
        return {
            "city": city_info.get("name", ""),
            "country": city_info.get("country", ""),
            "check_in": check_in,
            "days": [],
        }

    available_dates = sorted({
        (item.get("dt_txt") or "")[:10]
        for item in all_items
        if item.get("dt_txt")
    })

    if not check_in:
        start_date_str = available_dates[0]
    else:
        try:
            requested_date = datetime.strptime(check_in, "%Y-%m-%d").date()
            requested_str = requested_date.isoformat()

            # nếu ngày chọn không có trong forecast thì fallback về ngày đầu tiên đang có
            start_date_str = requested_str if requested_str in available_dates else available_dates[0]
        except ValueError:
            start_date_str = available_dates[0]

    start_index = available_dates.index(start_date_str)
    target_dates = available_dates[start_index:start_index + 3]

    grouped: dict[str, list[dict[str, Any]]] = {d: [] for d in target_dates}
    for item in all_items:
        d = (item.get("dt_txt") or "")[:10]
        if d in grouped:
            grouped[d].append(item)

    daily_forecasts = []
    for d in target_dates:
        items = grouped.get(d) or []
        if not items:
            continue

        selected = _pick_midday_item(items)
        mapped = _map_forecast_item(selected)

        temps = [
            (x.get("main") or {}).get("temp")
            for x in items
            if (x.get("main") or {}).get("temp") is not None
        ]
        if temps:
            mapped["temp_min"] = round(min(temps))
            mapped["temp_max"] = round(max(temps))

        daily_forecasts.append(mapped)

    return {
        "city": city_info.get("name", ""),
        "country": city_info.get("country", ""),
        "check_in": check_in,
        "resolved_start_date": start_date_str,
        "days": daily_forecasts,
    }
def get_hotel_detail_payload(hotel_id: str, check_in: str, adults: int = 2) -> dict[str, Any]:
    payload = _geoapify_get(
        "/v2/place-details",
        {"id": hotel_id, "features": "details", "lang": "vi"},
    )
    meta = _mock_hotel_meta(hotel_id)
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
        "amenities": meta["amenities"],
        "images": _hotel_gallery(hotel_id),
        "offers": offers,
        "price_from": meta["price_from"],
        "currency": "VND",
        "check_in": check_in,
        "adults": adults,
        "rating": {
            "overall": meta["rating_overall"],
            "reviews_count": None,
            "sentiments": {},
        },
    }