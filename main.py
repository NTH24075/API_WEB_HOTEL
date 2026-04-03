import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# ===== LOAD ENV =====
load_dotenv()
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

# ===== IMPORT ROUTERS =====
from api.hotels import router as hotels_router
from api.admin_hotels import router as admin_hotels_router
from api.auth import router as auth_router
from api.admin_users import router as admin_users_router
from api.receptionist_api import router as receptionist_router
from api.booking_hotel import hotel_router as booking_hotel_router
from api.booking_hotel import review_router as review_router
from api.admin_booking_api import router as admin_booking_router


# ===== INIT APP =====
app = FastAPI(title="Hotel Management API")

# ===== MIDDLEWARE =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# (optional - nếu dùng session)
app.add_middleware(
    SessionMiddleware,
    secret_key="your_secret_key"
)

# ===== STATIC + TEMPLATE =====
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ===== REGISTER ROUTERS =====
app.include_router(hotels_router, prefix="/api")   # API public
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(admin_hotels_router)
app.include_router(receptionist_router)
app.include_router(booking_hotel_router)
app.include_router(review_router)
app.include_router(admin_booking_router)


# ===== UI ROUTES =====

# Trang home
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "mapbox_token": MAPBOX_TOKEN,
        }
    )

# Trang list hotels (UI)
@app.get("/hotels")
def hotels_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )

# Trang chi tiết hotel
@app.get("/hotels/{hotel_id}")
def hotel_detail_page(
    request: Request,
    hotel_id: str,
    check_in: str = "2026-04-08",
    adults: int = 2,
):
    return templates.TemplateResponse(
        request=request,
        name="hotel_detail.html",
        context={
            "hotel_id": hotel_id,
            "check_in": check_in,
            "adults": adults,
            "mapbox_token": MAPBOX_TOKEN,
        },
    )

@app.get("/api/amenities")
async def get_amenities():
    from services.amadeus_service import get_hotel_detail_payload
    amenities = [
        {"id": 1, "name": "Wi-Fi", "icon": "wifi"},
        {"id": 2, "name": "Hồ bơi", "icon": "pool"},
        {"id": 3, "name": "Điều hòa", "icon": "ac_unit"},
        {"id": 4, "name": "Nhà hàng", "icon": "restaurant"},
        {"id": 5, "name": "Bãi đỗ xe", "icon": "local_parking"},
        {"id": 6, "name": "Phòng gym", "icon": "fitness_center"},
        {"id": 7, "name": "Spa", "icon": "spa"},
        {"id": 8, "name": "Lễ tân 24/7", "icon": "support_agent"},
    ]
    return amenities


@app.get("/api/weather")
async def get_weather(city_code: str, check_in: str, lang: str = "vi"):
    from services.amadeus_service import get_weather_forecast_3days
    try:
        return get_weather_forecast_3days(
            city_code=city_code,
            check_in=check_in,
            lang=lang,
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))