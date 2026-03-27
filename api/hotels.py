from fastapi import APIRouter, HTTPException, Query
import traceback

from services.amadeus_service import (
    get_hotel_detail_payload,
    search_hotels_by_city,
)

router = APIRouter()


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
