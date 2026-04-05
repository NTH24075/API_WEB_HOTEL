from fastapi import HTTPException
from core.database import get_conn


# =========================
# LẤY HOTEL ID CỦA RECEPTIONIST
# =========================
def get_receptionist_hotel_info(user_id: int):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                u.HotelId,
                h.HotelName,
                h.Address
            FROM Users u
            LEFT JOIN Hotels h ON u.HotelId = h.HotelId
            WHERE u.UserId = ?
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

        return {
            "hotel_id": row[0],
            "hotel_name": row[1] or "Dang cap nhat",
            "address": row[2] or "Dang cap nhat"
        }
    finally:
        conn.close()


# =========================
# LIST + FILTER BOOKING CỦA HOTEL MÌNH
# =========================
def get_my_hotel_bookings(user_id: int, from_date, to_date, booking_status, payment_status, keyword):
    hotel_info = get_receptionist_hotel_info(user_id)
    hotel_id = hotel_info["hotel_id"]

    conn = get_conn()
    try:
        cursor = conn.cursor()

        query = """
            SELECT
                b.BookingId,
                b.BookingCode,
                b.CheckInDate,
                b.CheckOutDate,
                b.TotalAmount,
                b.BookingStatus,
                b.PaymentStatus,
                u.FullName,
                u.Email,
                h.HotelName
            FROM Bookings b
            JOIN Users u ON b.UserId = u.UserId
            JOIN Hotels h ON b.HotelId = h.HotelId
            WHERE b.HotelId = ?
        """

        params = [hotel_id]

        if from_date:
            query += " AND b.CheckInDate >= ?"
            params.append(from_date)

        if to_date:
            query += " AND b.CheckOutDate <= ?"
            params.append(to_date)

        if booking_status:
            query += " AND b.BookingStatus = ?"
            params.append(booking_status)

        if payment_status:
            query += " AND b.PaymentStatus = ?"
            params.append(payment_status)

        if keyword:
            query += """
                AND (
                    u.FullName LIKE ?
                    OR u.Email LIKE ?
                    OR b.BookingCode LIKE ?
                )
            """
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        query += " ORDER BY b.CreatedAt DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return {
            "hotel": hotel_info,
            "message": "Lay danh sach booking thanh cong",
            "total": len(rows),
            "data": [
                {
                    "booking_id": r[0],
                    "booking_code": r[1],
                    "check_in": str(r[2]),
                    "check_out": str(r[3]),
                    "total_amount": float(r[4]),
                    "booking_status": r[5],
                    "payment_status": r[6],
                    "customer_name": r[7],
                    "email": r[8],
                    "hotel_name": r[9]
                }
                for r in rows
            ]
        }
    finally:
        conn.close()


# =========================
# CHI TIẾT BOOKING CỦA HOTEL MÌNH
# =========================
def get_my_hotel_booking_detail(user_id: int, booking_id: int):
    hotel_info = get_receptionist_hotel_info(user_id)
    hotel_id = hotel_info["hotel_id"]

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                b.BookingId,
                b.BookingCode,
                b.CheckInDate,
                b.CheckOutDate,
                b.TotalAmount,
                b.BookingStatus,
                b.PaymentStatus,
                u.FullName,
                u.Email,
                u.Phone,
                h.HotelName,
                b.ActualCheckInTime,
                b.ActualCheckOutTime
            FROM Bookings b
            JOIN Users u ON b.UserId = u.UserId
            JOIN Hotels h ON b.HotelId = h.HotelId
            WHERE b.BookingId = ? AND b.HotelId = ?
        """, (booking_id, hotel_id))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Booking khong ton tai hoac khong thuoc hotel nay")

        return {
            "booking_id": row[0],
            "booking_code": row[1],
            "check_in": str(row[2]),
            "check_out": str(row[3]),
            "total_amount": float(row[4]),
            "booking_status": row[5],
            "payment_status": row[6],
            "customer_name": row[7],
            "email": row[8],
            "phone": row[9],
            "hotel_name": row[10],
            "actual_check_in_time": str(row[11]) if row[11] else None,
            "actual_check_out_time": str(row[12]) if row[12] else None
        }
    finally:
        conn.close()

# =========================
# CHECK BOOKING CÓ THUỘC HOTEL KHÔNG
# =========================
def ensure_booking_belongs_to_hotel(cursor, booking_id: int, hotel_id: int):
    cursor.execute("""
        SELECT BookingId
        FROM Bookings
        WHERE BookingId = ? AND HotelId = ?
    """, (booking_id, hotel_id))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Booking khong ton tai hoac khong thuoc hotel nay")


# =========================
# CHECK-IN BOOKING
# =========================
def check_in_my_hotel_booking(user_id: int, booking_id: int):
    hotel_info = get_receptionist_hotel_info(user_id)
    hotel_id = hotel_info["hotel_id"]

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT BookingStatus, ActualCheckInTime, ActualCheckOutTime
            FROM Bookings
            WHERE BookingId = ? AND HotelId = ?
        """, (booking_id, hotel_id))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, "Booking khong ton tai")

        status = (row[0] or "").strip().lower()
        actual_check_in = row[1]
        actual_check_out = row[2]

        if status == "cancelled":
            raise HTTPException(400, "Booking da bi huy, khong the check-in")

        if actual_check_out is not None:
            raise HTTPException(400, "Booking da check-out roi")

        if actual_check_in is not None:
            raise HTTPException(400, "Booking da check-in roi")

        cursor.execute("""
            UPDATE Bookings
            SET ActualCheckInTime = GETDATE()
            WHERE BookingId = ? AND HotelId = ?
        """, (booking_id, hotel_id))

        conn.commit()
        return {"message": "Check-in thanh cong"}
    finally:
        conn.close()

# =========================
# CHECK-OUT BOOKING
# =========================
def check_out_my_hotel_booking(user_id: int, booking_id: int):
    hotel_info = get_receptionist_hotel_info(user_id)
    hotel_id = hotel_info["hotel_id"]

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT BookingStatus, ActualCheckInTime, ActualCheckOutTime
            FROM Bookings
            WHERE BookingId = ? AND HotelId = ?
        """, (booking_id, hotel_id))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, "Booking khong ton tai")

        status = (row[0] or "").strip().lower()
        actual_check_in = row[1]
        actual_check_out = row[2]

        if status == "cancelled":
            raise HTTPException(400, "Booking da bi huy, khong the check-out")

        if actual_check_in is None:
            raise HTTPException(400, "Chua check-in thi khong the check-out")

        if actual_check_out is not None:
            raise HTTPException(400, "Booking da check-out roi")

        cursor.execute("""
            UPDATE Bookings
            SET ActualCheckOutTime = GETDATE()
            WHERE BookingId = ? AND HotelId = ?
        """, (booking_id, hotel_id))

        conn.commit()
        return {"message": "Check-out thanh cong"}
    finally:
        conn.close()

# =========================
# HỦY BOOKING
# =========================
def cancel_my_hotel_booking(user_id: int, booking_id: int):
    hotel_info = get_receptionist_hotel_info(user_id)
    hotel_id = hotel_info["hotel_id"]

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT BookingStatus, ActualCheckInTime, ActualCheckOutTime
            FROM Bookings
            WHERE BookingId = ? AND HotelId = ?
        """, (booking_id, hotel_id))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, "Booking khong ton tai")

        status = (row[0] or "").strip().lower()
        actual_check_in = row[1]
        actual_check_out = row[2]

        if status == "cancelled":
            raise HTTPException(400, "Booking da bi huy truoc do")

        if actual_check_in is not None:
            raise HTTPException(400, "Khach da check-in, khong the huy")

        if actual_check_out is not None:
            raise HTTPException(400, "Booking da hoan tat, khong the huy")

        cursor.execute("""
            UPDATE Bookings
            SET BookingStatus = 'Cancelled'
            WHERE BookingId = ? AND HotelId = ?
        """, (booking_id, hotel_id))

        conn.commit()
        return {"message": "Huy booking thanh cong"}
    finally:
        conn.close()


# =========================
# LIST PAYMENT CỦA HOTEL MÌNH
# =========================
def get_my_hotel_payments(user_id: int):
    hotel_info = get_receptionist_hotel_info(user_id)
    hotel_id = hotel_info["hotel_id"]

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                p.PaymentId,
                p.Amount,
                p.PaymentStatus,
                p.PaymentMethod,
                p.PaidAt,
                b.BookingCode,
                u.FullName
            FROM Payments p
            JOIN Bookings b ON p.BookingId = b.BookingId
            JOIN Users u ON b.UserId = u.UserId
            WHERE b.HotelId = ?
            ORDER BY p.CreatedAt DESC
        """, (hotel_id,))

        rows = cursor.fetchall()

        return {
            "hotel": hotel_info,
            "message": "Lay danh sach payment thanh cong",
            "data": [
                {
                    "payment_id": r[0],
                    "amount": float(r[1]),
                    "payment_status": r[2],
                    "payment_method": r[3],
                    "paid_at": str(r[4]) if r[4] else None,
                    "booking_code": r[5],
                    "customer_name": r[6]
                }
                for r in rows
            ]
        }
    finally:
        conn.close()