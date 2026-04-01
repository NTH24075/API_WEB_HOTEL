import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
# ===== IMPORT ROUTERS (controller) =====
from api.hotels import router as hotels_router

load_dotenv()
from api.admin_hotels import router as admin_hotels_router
from api.auth import router as auth_router
from api.admin_users import router as admin_users_router
from api.booking_hotel import hotel_router as booking_hotel_router
from api.booking_hotel import review_router as review_router


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

# ===== STATIC + TEMPLATE =====
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(hotels_router)

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

@app.get("/hotels")
def hotels_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})
# ===== REGISTER ROUTERS =====
app.include_router(hotels_router)          # public hotel API (Geoapify)
app.include_router(auth_router)            # login/register
app.include_router(admin_users_router)     # admin quản lý user
app.include_router(admin_hotels_router)    # admin quản lý hotel
app.include_router(booking_hotel_router)
app.include_router(review_router)

# ===== HOME PAGE =====
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "mapbox_token": MAPBOX_TOKEN,
        }
    )

# ===== HOTEL DETAIL PAGE (UI) =====
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