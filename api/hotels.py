from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from core.database import get_conn
import traceback
from services.amadeus_service import (
    get_hotel_detail_payload,
    search_hotels_by_city,
    get_weather_forecast_3days,
)

class FavoritePayload(BaseModel):
    user_id: int
    hotel_id: str

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/api/hotels")
def api_list_hotels(
    city_code: str | None = Query(None),
    city: str | None = Query(None),
    max_results: int = Query(12, ge=1, le=30),
):
    try:
        return search_hotels_by_city(
            city_code=city_code,
            city=city,
            max_results=max_results,
        )
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

        # kiểm tra user tồn tại
        # curs.execute("SELECT UserId FROM Users WHERE UserId = ?", (user_id,))
        # user = curs.fetchone()

        # if not user:
        #     raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

        # kiểm tra đã thích chưa
        curs.execute(
            "SELECT FavoriteId FROM FavoriteHotels WHERE UserId = ? AND HotelId = ?",
            (user_id, hotel_id)
        )
        existed = curs.fetchone()

        if existed:
            raise HTTPException(status_code=400, detail="Khách sạn đã có trong yêu thích")

        # thêm favorite
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


