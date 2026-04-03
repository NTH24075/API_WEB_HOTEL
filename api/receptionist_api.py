from fastapi import APIRouter, Depends
from schemas.receptionist_schemas import (
    AssignHotelServiceRequest,
    UpdateHotelServiceRequest
)
from services.receptionist_service import (
    get_all_active_services,
    get_my_hotel_services,
    assign_service_to_my_hotel,
    update_my_hotel_service,
    delete_my_hotel_service
)
from core.dependencies import require_receptionist
router = APIRouter(prefix="/receptionist", tags=["Receptionist"])


@router.get("/services")
def get_services_for_assignment(receptionist=Depends(require_receptionist)):
    return get_all_active_services()


@router.get("/hotel-services")
def get_current_hotel_services(receptionist=Depends(require_receptionist)):
    return get_my_hotel_services(receptionist["user_id"])


@router.post("/hotel-services")
def assign_hotel_service(
    data: AssignHotelServiceRequest,
    receptionist=Depends(require_receptionist)
):
    return assign_service_to_my_hotel(
        user_id=receptionist["user_id"],
        service_id=data.service_id,
        custom_price=data.custom_price,
        is_available=data.is_available
    )


@router.put("/hotel-services/{hotel_service_id}")
def update_hotel_service(
    hotel_service_id: int,
    data: UpdateHotelServiceRequest,
    receptionist=Depends(require_receptionist)
):
    return update_my_hotel_service(
        user_id=receptionist["user_id"],
        hotel_service_id=hotel_service_id,
        custom_price=data.custom_price,
        is_available=data.is_available
    )


@router.delete("/hotel-services/{hotel_service_id}")
def remove_hotel_service(
    hotel_service_id: int,
    receptionist=Depends(require_receptionist)
):
    return delete_my_hotel_service(
        user_id=receptionist["user_id"],
        hotel_service_id=hotel_service_id
    )