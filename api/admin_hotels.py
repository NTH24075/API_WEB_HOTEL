from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import require_admin
from schemas.admin_hotels_schemas import (
    AdminHotelSearchRequest,
    ImportHotelsByCityRequest,
)
from services.admin_hotel_service import (
    delete_hotel_by_id,
    import_hotels_by_city_to_db,
    search_hotels_from_db,
)

router = APIRouter(prefix="/admin/hotels", tags=["Admin Hotels"])


@router.post("/import")
def import_hotels(data: ImportHotelsByCityRequest, admin=Depends(require_admin)):
    try:
        return import_hotels_by_city_to_db(
            city=data.city,
            max_results=data.max_results,
            use_placeholder_for_null=False,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi import khách sạn: {str(e)}")


@router.post("/search")
def search_hotels(data: AdminHotelSearchRequest, admin=Depends(require_admin)):
    try:
        return search_hotels_from_db(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm khách sạn: {str(e)}")


@router.delete("/{hotel_id}")
def delete_hotel(hotel_id: int, admin=Depends(require_admin)):
    try:
        return delete_hotel_by_id(hotel_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa khách sạn: {str(e)}")