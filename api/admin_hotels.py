from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import require_admin
from schemas.admin_hotels_schemas import ImportHotelsByCityRequest
from services.admin_hotel_service import import_hotels_by_city_to_db

router = APIRouter(prefix="/admin/hotels", tags=["Admin Hotels"])


@router.post("/import")
def import_hotels(data: ImportHotelsByCityRequest, admin=Depends(require_admin)):
    try:
        return import_hotels_by_city_to_db(
            city=data.city,
            max_results=data.max_results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))