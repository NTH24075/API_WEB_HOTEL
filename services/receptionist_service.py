from fastapi import HTTPException
from core.database import get_conn


def get_receptionist_hotel_id(user_id: int) -> int:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT HotelId
            FROM Users
            WHERE UserId = ?
        """, (user_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Khong tim thay user")

        hotel_id = row[0]
        if hotel_id is None:
            raise HTTPException(
                status_code=400,
                detail="Receptionist chua duoc gan khach san"
            )

        return hotel_id
    finally:
        conn.close()


def get_all_active_services():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ServiceId,
                ServiceName,
                Description,
                Price,
                Unit,
                IsActive
            FROM Services
            WHERE IsActive = 1
            ORDER BY ServiceName
        """)
        rows = cursor.fetchall()

        result = []
        for row in rows:
            result.append({
                "service_id": row[0],
                "service_name": row[1],
                "description": row[2],
                "price": float(row[3]),
                "unit": row[4],
                "is_active": bool(row[5]),
            })

        return result
    finally:
        conn.close()


def get_my_hotel_services(user_id: int):
    hotel_id = get_receptionist_hotel_id(user_id)

    conn = get_conn()
    try:
        cursor = conn.cursor()

        # Lấy thông tin khách sạn
        cursor.execute("""
            SELECT HotelId, HotelName, Address
            FROM Hotels
            WHERE HotelId = ?
        """, (hotel_id,))
        hotel_row = cursor.fetchone()

        if not hotel_row:
            raise HTTPException(status_code=404, detail="Khong tim thay khach san")

        hotel_info = {
            "hotel_id": hotel_row[0],
            "hotel_name": hotel_row[1] or "Dang cap nhat",
            "address": hotel_row[2] or "Dang cap nhat"
        }

        # Lấy danh sách service của hotel
        cursor.execute("""
            SELECT
                hs.HotelServiceId,
                hs.HotelId,
                hs.ServiceId,
                s.ServiceName,
                s.Description,
                s.Price,
                hs.CustomPrice,
                s.Unit,
                s.IsActive,
                hs.IsAvailable
            FROM HotelServices hs
            INNER JOIN Services s ON hs.ServiceId = s.ServiceId
            WHERE hs.HotelId = ?
            ORDER BY s.ServiceName
        """, (hotel_id,))
        rows = cursor.fetchall()

        items = []
        for row in rows:
            default_price = float(row[5])
            custom_price = float(row[6]) if row[6] is not None else None
            final_price = custom_price if custom_price is not None else default_price

            items.append({
                "hotel_service_id": row[0],
                "hotel_id": row[1],
                "service_id": row[2],
                "service_name": row[3],
                "description": row[4],
                "default_price": default_price,
                "custom_price": custom_price,
                "final_price": final_price,
                "unit": row[7],
                "is_active": bool(row[8]),
                "is_available": bool(row[9]),
            })

        return {
            "hotel": hotel_info,
            "items": items
        }
    finally:
        conn.close()


def assign_service_to_my_hotel(
    user_id: int,
    service_id: int,
    custom_price=None,
    is_available: bool = True
):
    hotel_id = get_receptionist_hotel_id(user_id)

    conn = get_conn()
    try:
        cursor = conn.cursor()

        # check service tồn tại và đang active
        cursor.execute("""
            SELECT ServiceId, IsActive
            FROM Services
            WHERE ServiceId = ?
        """, (service_id,))
        service_row = cursor.fetchone()

        if not service_row:
            raise HTTPException(status_code=404, detail="Service khong ton tai")

        if not bool(service_row[1]):
            raise HTTPException(status_code=400, detail="Service dang khong hoat dong")

        # check trùng
        cursor.execute("""
            SELECT HotelServiceId
            FROM HotelServices
            WHERE HotelId = ? AND ServiceId = ?
        """, (hotel_id, service_id))
        existed = cursor.fetchone()

        if existed:
            raise HTTPException(
                status_code=400,
                detail="Service nay da duoc gan cho khach san"
            )

        cursor.execute("""
            INSERT INTO HotelServices (
                HotelId,
                ServiceId,
                CustomPrice,
                IsAvailable
            )
            VALUES (?, ?, ?, ?)
        """, (
            hotel_id,
            service_id,
            custom_price,
            1 if is_available else 0
        ))

        conn.commit()

        return {
            "message": "Gan service vao hotel thanh cong",
            "hotel_id": hotel_id,
            "service_id": service_id
        }
    finally:
        conn.close()


def update_my_hotel_service(
    user_id: int,
    hotel_service_id: int,
    custom_price=None,
    is_available=None
):
    hotel_id = get_receptionist_hotel_id(user_id)

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT HotelServiceId
            FROM HotelServices
            WHERE HotelServiceId = ? AND HotelId = ?
        """, (hotel_service_id, hotel_id))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Khong tim thay service cua hotel nay"
            )

        update_fields = []
        params = []

        if custom_price is not None:
            update_fields.append("CustomPrice = ?")
            params.append(custom_price)

        if is_available is not None:
            update_fields.append("IsAvailable = ?")
            params.append(1 if is_available else 0)

        if not update_fields:
            raise HTTPException(status_code=400, detail="Khong co du lieu de cap nhat")

        sql = f"""
            UPDATE HotelServices
            SET {", ".join(update_fields)}
            WHERE HotelServiceId = ? AND HotelId = ?
        """
        params.extend([hotel_service_id, hotel_id])

        cursor.execute(sql, params)
        conn.commit()

        return {"message": "Cap nhat hotel service thanh cong"}
    finally:
        conn.close()


def delete_my_hotel_service(user_id: int, hotel_service_id: int):
    hotel_id = get_receptionist_hotel_id(user_id)

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT HotelServiceId
            FROM HotelServices
            WHERE HotelServiceId = ? AND HotelId = ?
        """, (hotel_service_id, hotel_id))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Khong tim thay service cua hotel nay"
            )

        cursor.execute("""
            DELETE FROM HotelServices
            WHERE HotelServiceId = ? AND HotelId = ?
        """, (hotel_service_id, hotel_id))

        conn.commit()

        return {"message": "Xoa service khoi hotel thanh cong"}
    finally:
        conn.close()