import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# ===== LOAD ENV =====
load_dotenv()
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

# ===== IMPORT ROUTERS =====
from api.hotels import router as hotels_router
from api.admin_hotels import router as admin_hotels_router

# Route for account
from api.auth import router as auth_router
from api.admin_users import router as admin_users_router
from api.user_account import router as user_account_router
from api.booking_hotel import hotel_router, review_router
from api.receptionist_api import router as receptionist_router
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
app.include_router(hotels_router)          # public hotel API (Geoapify)
app.include_router(auth_router)            # login/register
app.include_router(admin_users_router)     # admin quản lý user
app.include_router(admin_hotels_router)    # admin quản lý hotel
app.include_router(user_account_router)
app.include_router(hotel_router)
app.include_router(review_router)
app.include_router(receptionist_router)  
app.include_router(admin_booking_router)  # approved delete request from user

# ===== UI ROUTES =====

# Trang home
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "mapbox_token": MAPBOX_TOKEN,
            "google_client_id": os.getenv("GOOGLE_CLIENT_ID"),
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

# ===== Route regis / login UI
load_dotenv()
@app.get("/auth-page")
def auth_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="/user/auth.html",
        context={
            "google_client_id": os.getenv("GOOGLE_CLIENT_ID")
        }
    )
@app.get("/admin-user-page")
def admin_user_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="/user/admin_user.html",
        context={}
    )

@app.get("/user-info-page")
def user_info_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="/user/user_info.html",
        context={}
    )

# ===== HOTEL DETAIL PAGE (UI) =====
@app.get("/hotels/{hotel_id}")
def hotel_detail_page(
    request: Request,
    hotel_id: str,
    check_in: str = "2026-04-08",
    adults: int = 2,
    check_out: str = "",
):
    return templates.TemplateResponse(
        request=request,
        name="hotel_detail.html",
        context={
            "hotel_id": hotel_id,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "mapbox_token": MAPBOX_TOKEN,
        },
    )
#--- Admin hotel management UI

@app.get("/admin/hotels-page", response_class=HTMLResponse)
def admin_hotels_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/admin_hotel.html",
        context={}
    )
@app.get("/receptionist/hotel-services-page", response_class=HTMLResponse)
def receptionist_hotel_services_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="receptionist/receptionist_hotel_service.html",
        context={}
    )
