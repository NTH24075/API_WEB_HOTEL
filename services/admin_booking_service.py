from fastapi import HTTPException
from core.database import get_conn


def get_all_bookings(from_date, to_date, booking_status, payment_status, keyword):
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
            WHERE 1=1
        """

        params = []

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


def get_booking_detail(booking_id):
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
                h.HotelName
            FROM Bookings b
            JOIN Users u ON b.UserId = u.UserId
            JOIN Hotels h ON b.HotelId = h.HotelId
            WHERE b.BookingId = ?
        """, (booking_id,))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, "Booking khong ton tai")

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
            "hotel_name": row[10]
        }

    finally:
        conn.close()


def check_in_booking(booking_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Bookings
            SET ActualCheckInTime = GETDATE()
            WHERE BookingId = ?
        """, (booking_id,))

        if cursor.rowcount == 0:
            raise HTTPException(404, "Booking khong ton tai")

        conn.commit()
        return {"message": "Check-in thanh cong"}

    finally:
        conn.close()


def check_out_booking(booking_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Bookings
            SET ActualCheckOutTime = GETDATE()
            WHERE BookingId = ?
        """, (booking_id,))

        if cursor.rowcount == 0:
            raise HTTPException(404, "Booking khong ton tai")

        conn.commit()
        return {"message": "Check-out thanh cong"}

    finally:
        conn.close()


def cancel_booking(booking_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Bookings
            SET BookingStatus = 'Cancelled'
            WHERE BookingId = ?
        """, (booking_id,))

        if cursor.rowcount == 0:
            raise HTTPException(404, "Booking khong ton tai")

        conn.commit()
        return {"message": "Huy booking thanh cong"}

    finally:
        conn.close()


def get_all_payments():
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
            ORDER BY p.CreatedAt DESC
        """)

        rows = cursor.fetchall()

        return {
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