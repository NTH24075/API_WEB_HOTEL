from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from datetime import datetime
from core.database import get_conn
from core.dependencies import get_current_user
from schemas.roomoffer_schemas import (
    CurrentUserAndRoomOfferResponse,
    CreateReviewRequest,
)
from datetime import datetime
from fastapi import Depends, HTTPException


hotel_router = APIRouter(prefix="/api/bookinghotels", tags=["Booking And Payment"])


@hotel_router.post("/create-booking/{room_offer_id}")
def create_booking(
    room_offer_id: int,
    check_in_date: str,
    check_out_date: str,
    adults: int,
    children: int = 0,
    number_of_rooms: int = 1,
    special_request: str = None,
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("UserId") or current_user.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Không xác định được user"
        )

    cursor = db.cursor()

    try:
        # 1. Lấy room offer
        query = """
            SELECT
                OfferId,
                HotelId,
                Capacity,
                PricePerNight,
                AvailableQuantity
            FROM RoomOffers
            WHERE OfferId = ?
        """
        cursor.execute(query, (room_offer_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy phòng")

        offer_id, hotel_id, capacity, price_per_night, available_qty = row

        # 2. Validate dữ liệu
        try:
            check_in = datetime.strptime(check_in_date, "%Y-%m-%d")
            check_out = datetime.strptime(check_out_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Ngày phải đúng định dạng YYYY-MM-DD, ví dụ: 2026-04-30"
            )

        if check_in >= check_out:
            raise HTTPException(status_code=400, detail="Ngày check-out phải lớn hơn ngày check-in")

        total_people = adults + children
        if total_people > capacity:
            raise HTTPException(status_code=400, detail="Số người vượt quá sức chứa phòng")

        if number_of_rooms > available_qty:
            raise HTTPException(status_code=400, detail="Không đủ số phòng")

        # 3. Tính tiền
        nights = (check_out - check_in).days
        total_amount = float(price_per_night) * number_of_rooms * nights

        # 4. Tạo BookingCode
        import uuid
        booking_code = str(uuid.uuid4())[:10]

        # 5. Insert booking + lấy BookingId ngay sau insert
        insert_query = """
            INSERT INTO Bookings (
                UserId,
                HotelId,
                OfferId,
                BookingCode,
                CheckInDate,
                CheckOutDate,
                Adults,
                Children,
                NumberOfRooms,
                TotalAmount,
                BookingStatus,
                PaymentStatus,
                SpecialRequest,
                CreatedAt
            )
            OUTPUT INSERTED.BookingId
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """

        cursor.execute(
            insert_query,
            (
                user_id,
                hotel_id,
                offer_id,
                booking_code,
                check_in_date,
                check_out_date,
                adults,
                children,
                number_of_rooms,
                total_amount,
                "Pending",
                "Unpaid",
                special_request
            )
        )

        inserted_row = cursor.fetchone()
        if not inserted_row or inserted_row[0] is None:
            db.rollback()
            raise HTTPException(status_code=500, detail="Không lấy được BookingId sau khi tạo booking")

        booking_id = int(inserted_row[0])

        # 6. Update số phòng
        update_query = """
            UPDATE RoomOffers
            SET AvailableQuantity = AvailableQuantity - ?
            WHERE OfferId = ?
        """
        cursor.execute(update_query, (number_of_rooms, offer_id))

        db.commit()

        return {
            "message": "Tạo booking thành công",
            "booking_id": booking_id,
            "booking_code": booking_code,
            "total_amount": total_amount
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
    finally:
        cursor.close()


@hotel_router.post("/add-services/{booking_id}")
def add_services_to_booking(
    booking_id: int,
    service_items: list[dict],  # [{"hotelservice_id": 1, "quantity": 2}]
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    cursor = db.cursor()

    try:
        # 1. Check booking
        cursor.execute("""
            SELECT TotalAmount
            FROM Bookings
            WHERE BookingId = ?
        """, (booking_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Booking không tồn tại")

        current_total = float(row[0])
        total_service_cost = 0
        added_services = []

        # 2. Validate input
        if not service_items or not isinstance(service_items, list):
            raise HTTPException(400, "service_items phải là list")

        # 3. Loop từng service
        for index, item in enumerate(service_items, start=1):

            hotelservice_id = item.get("hotelservice_id")
            quantity = item.get("quantity", 1)

            if hotelservice_id is None:
                raise HTTPException(
                    400, f"Thiếu hotelservice_id ở phần tử {index}"
                )

            try:
                hotelservice_id = int(hotelservice_id)
                quantity = int(quantity)
            except:
                raise HTTPException(
                    400, f"hotelservice_id hoặc quantity sai kiểu ở phần tử {index}"
                )

            if quantity <= 0:
                raise HTTPException(
                    400, f"quantity phải > 0 ở phần tử {index}"
                )

            # 🔥 Lấy giá từ HotelServices (ưu tiên CustomPrice)
            cursor.execute("""
                SELECT 
                    hs.CustomPrice,
                    s.Price
                FROM HotelServices hs
                JOIN Services s ON hs.ServiceId = s.ServiceId
                WHERE hs.HotelServiceId = ? AND hs.IsAvailable = 1
            """, (hotelservice_id,))

            service = cursor.fetchone()

            if not service:
                raise HTTPException(
                    404,
                    f"HotelServiceId = {hotelservice_id} không tồn tại hoặc không khả dụng"
                )

            custom_price, default_price = service

            unit_price = float(custom_price) if custom_price else float(default_price)
            total_price = unit_price * quantity

            # 🔥 Insert dùng HotelServiceId
            cursor.execute("""
                INSERT INTO BookingServices (
                    BookingId,
                    HotelServiceId,
                    Quantity,
                    UnitPrice,
                    TotalPrice,
                    UsedAt
                )
                VALUES (?, ?, ?, ?, ?, NULL)
            """, (
                booking_id,
                hotelservice_id,
                quantity,
                unit_price,
                total_price
            ))

            total_service_cost += total_price

            added_services.append({
                "hotelservice_id": hotelservice_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price
            })

        # 4. Update Booking
        new_total = current_total + total_service_cost

        cursor.execute("""
            UPDATE Bookings
            SET TotalAmount = ?
            WHERE BookingId = ?
        """, (new_total, booking_id))

        db.commit()

        return {
            "message": "Thêm dịch vụ thành công",
            "booking_id": booking_id,
            "added_services": added_services,
            "added_service_cost": total_service_cost,
            "new_total_amount": new_total
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Lỗi hệ thống: {str(e)}")
    finally:
        cursor.close()

@hotel_router.delete("/delete-booking/{booking_id}")
def delete_booking(
    booking_id: int,
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    cursor = db.cursor()

    try:
        user_id = current_user.get("UserId") or current_user.get("user_id")

        # 1. Check booking
        cursor.execute("""
            SELECT UserId, OfferId, NumberOfRooms
            FROM Bookings
            WHERE BookingId = ?
        """, (booking_id,))
        
        row = cursor.fetchone()

        if not row:
            raise HTTPException(404, "Booking không tồn tại")

        booking_user_id, offer_id, number_of_rooms = row

        # 2. Check quyền
        if booking_user_id != user_id:
            raise HTTPException(403, "Không có quyền")

        # 3. Xoá BookingServices
        cursor.execute("""
            DELETE FROM BookingServices
            WHERE BookingId = ?
        """, (booking_id,))

        # 4. Xoá Payments 
        cursor.execute("""
            DELETE FROM Payments
            WHERE BookingId = ?
        """, (booking_id,))

        # 5. Trả lại phòng
        cursor.execute("""
            UPDATE RoomOffers
            SET AvailableQuantity = AvailableQuantity + ?
            WHERE OfferId = ?
        """, (number_of_rooms, offer_id))

        # 6. Xoá booking
        cursor.execute("""
            DELETE FROM Bookings
            WHERE BookingId = ?
        """, (booking_id,))

        db.commit()

        return {
            "message": "Xoá booking thành công",
            "booking_id": booking_id
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()



@hotel_router.post("/create-payment/{booking_id}")
def create_payment(
    booking_id: int,
    payment_method: str = Query("Cash", include_in_schema=False),  
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    cursor = db.cursor()

    try:
    
        # 1. Check booking
        # ========================
        cursor.execute("""
            SELECT TotalAmount, PaymentStatus, BookingStatus
            FROM Bookings
            WHERE BookingId = ?
        """, (booking_id,))
        
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(404, "Booking không tồn tại")

        total_amount, payment_status, booking_status = booking

        # ========================
        # 2. Validate trạng thái
        # ========================
        if booking_status == "Cancelled":
            raise HTTPException(400, "Booking đã bị huỷ, không thể thanh toán")

        if payment_status == "Paid":
            raise HTTPException(400, "Booking đã được thanh toán")

        # ========================
        # 3. Insert Payment + lấy ID
        # ========================
        cursor.execute("""
            INSERT INTO Payments (
                BookingId,
                Amount,
                PaymentMethod,
                PaymentStatus,
                PaidAt,
                CreatedAt
            )
            OUTPUT INSERTED.PaymentId
            VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
        """, (
            booking_id,
            total_amount,
            payment_method,   # luôn = "Cash"
            "UnPaid"
        ))

        payment_id = int(cursor.fetchone()[0])

        # ========================
        # 4. Update Booking
        # ========================
        cursor.execute("""
            UPDATE Bookings
            SET PaymentStatus = ?, BookingStatus = ?, UpdatedAt = GETDATE()
            WHERE BookingId = ?
        """, (
            "UnPaid",
            "UnConfirmed",
            booking_id
        ))

        db.commit()

        return {
            "message": "Tạo thanh toán thành công",
            "payment_id": payment_id,
            "booking_id": booking_id,
            "amount": total_amount,
            "payment_method": payment_method  # luôn là Cash
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Lỗi hệ thống: {str(e)}")
    finally:
        cursor.close()

@hotel_router.post("/confirm-payment/{payment_id}")
def confirm_payment(
    payment_id: int,
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    cursor = db.cursor()

    try:
        # ========================
        # 1. Check payment tồn tại
        # ========================
        cursor.execute("""
            SELECT PaymentId, BookingId, Amount, PaymentStatus
            FROM Payments
            WHERE PaymentId = ?
        """, (payment_id,))
        
        payment = cursor.fetchone()

        if not payment:
            raise HTTPException(404, "Payment không tồn tại")

        payment_id_db, booking_id, amount, payment_status = payment

        # ========================
        # 2. Validate payment status
        # ========================
        if payment_status == "Paid":
            raise HTTPException(400, "Payment này đã được xác nhận trước đó")

        # ========================
        # 3. Check booking liên quan
        # ========================
        cursor.execute("""
            SELECT BookingStatus, PaymentStatus
            FROM Bookings
            WHERE BookingId = ?
        """, (booking_id,))
        
        booking = cursor.fetchone()

        if not booking:
            raise HTTPException(404, "Booking không tồn tại")

        booking_status, booking_payment_status = booking

        if booking_status == "Cancelled":
            raise HTTPException(400, "Booking đã bị huỷ, không thể xác nhận thanh toán")

        # ========================
        # 4. Update Payments
        # ========================
        cursor.execute("""
            UPDATE Payments
            SET PaymentStatus = ?, PaidAt = GETDATE()
            WHERE PaymentId = ?
        """, (
            "Paid",
            payment_id
        ))

        # ========================
        # 5. Update Bookings
        # ========================
        cursor.execute("""
            UPDATE Bookings
            SET PaymentStatus = ?, BookingStatus = ?, UpdatedAt = GETDATE()
            WHERE BookingId = ?
        """, (
            "Paid",
            "Confirmed",
            booking_id
        ))

        db.commit()

        return {
            "message": "Xác nhận thanh toán thành công",
            "payment_id": payment_id,
            "booking_id": booking_id,
            "amount": float(amount),
            "payment_status": "Paid",
            "booking_status": "Confirmed"
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Lỗi hệ thống: {str(e)}")
    finally:
        cursor.close()

@hotel_router.delete("/delete-payment/{payment_id}")
def delete_payment(
    payment_id: int,
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    cursor = db.cursor()

    try:
        # ========================
        # 1. Kiểm tra payment tồn tại
        # ========================
        cursor.execute("""
            SELECT PaymentId, BookingId, PaymentStatus
            FROM Payments
            WHERE PaymentId = ?
        """, (payment_id,))
        
        payment = cursor.fetchone()

        if not payment:
            raise HTTPException(404, "Payment không tồn tại")

        payment_id_db, booking_id, payment_status = payment

        # ========================
        # 2. Không cho xoá payment đã thanh toán
        # ========================
        if payment_status == "Paid":
            raise HTTPException(400, "Không thể xoá payment đã thanh toán")

        # ========================
        # 3. Xoá payment
        # ========================
        cursor.execute("""
            DELETE FROM Payments
            WHERE PaymentId = ?
        """, (payment_id,))

        # ========================
        # 4. Kiểm tra booking còn payment UnPaid nào không
        # ========================
        cursor.execute("""
            SELECT COUNT(*)
            FROM Payments
            WHERE BookingId = ? AND PaymentStatus = 'UnPaid'
        """, (booking_id,))
        
        unpaid_count = cursor.fetchone()[0]

        # ========================
        # 5. Update lại Bookings nếu không còn payment chờ
        # ========================
        if unpaid_count == 0:
            cursor.execute("""
                UPDATE Bookings
                SET PaymentStatus = ?, BookingStatus = ?, UpdatedAt = GETDATE()
                WHERE BookingId = ?
            """, (
                "Unpaid",
                "Pending",
                booking_id
            ))

        db.commit()

        return {
            "message": "Xoá payment thành công",
            "payment_id": payment_id,
            "booking_id": booking_id
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Lỗi hệ thống: {str(e)}")
    finally:
        cursor.close()


@hotel_router.get("/my-paid-bookings")
def get_my_paid_bookings(
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    cursor = db.cursor()

    try:
        user_id = current_user["user_id"]

        cursor.execute("""
            SELECT
                b.BookingId,
                b.BookingCode,
                b.CheckInDate,
                b.CheckOutDate,
                b.Adults,
                b.Children,
                b.NumberOfRooms,
                b.TotalAmount,
                b.BookingStatus,
                b.PaymentStatus,
                b.SpecialRequest,
                b.CreatedAt,

                ro.OfferId,
                ro.RoomType,
                ro.Description,
                ro.Capacity,
                ro.PricePerNight,
                ro.Currency,
                ro.AvailableQuantity,
                ro.CheckInDate AS OfferCheckInDate,
                ro.CheckOutDate AS OfferCheckOutDate,
                ro.CancellationPolicy,
                ro.Amenities,

                p.PaymentId,
                p.Amount,
                p.PaymentMethod,
                p.PaymentStatus AS PaymentTableStatus,
                p.PaidAt,
                p.Note

            FROM Bookings b
            LEFT JOIN RoomOffers ro ON b.OfferId = ro.OfferId
            LEFT JOIN Payments p ON b.BookingId = p.BookingId
            WHERE b.UserId = ?
              AND b.PaymentStatus = 'Paid'
              AND p.PaymentStatus = 'Paid'
            ORDER BY b.CreatedAt DESC
        """, (user_id,))

        rows = cursor.fetchall()

        if not rows:
            return {
                "message": "Người dùng chưa có booking nào đã thanh toán",
                "data": []
            }

        data = []
        for row in rows:
            data.append({
                "booking_id": row[0],
                "booking_code": row[1],
                "check_in_date": str(row[2]) if row[2] else None,
                "check_out_date": str(row[3]) if row[3] else None,
                "adults": row[4],
                "children": row[5],
                "number_of_rooms": row[6],
                "total_amount": float(row[7]) if row[7] is not None else 0,
                "booking_status": row[8],
                "payment_status": row[9],
                "special_request": row[10],
                "created_at": str(row[11]) if row[11] else None,

                "room_offer": {
                    "offer_id": row[12],
                    "room_type": row[13],
                    "description": row[14],
                    "capacity": row[15],
                    "price_per_night": float(row[16]) if row[16] is not None else 0,
                    "currency": row[17],
                    "available_quantity": row[18],
                    "offer_check_in_date": str(row[19]) if row[19] else None,
                    "offer_check_out_date": str(row[20]) if row[20] else None,
                    "cancellation_policy": row[21],
                    "amenities": row[22]
                },

                "payment": {
                    "payment_id": row[23],
                    "amount": float(row[24]) if row[24] is not None else 0,
                    "payment_method": row[25],
                    "payment_status": row[26],
                    "paid_at": str(row[27]) if row[27] else None,
                    "note": row[28]
                }
            })

        return {
            "message": "Lấy danh sách booking đã thanh toán thành công",
            "user_id": user_id,
            "data": data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi hệ thống: {str(e)}"
        )
    finally:
        cursor.close()





















# Router cho Reviews
review_router = APIRouter(prefix="/api/reviews", tags=["Reviews"])


@review_router.post("/create")
def create_review(
    payload: CreateReviewRequest,
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("UserId") or current_user.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không xác định được người dùng"
        )

    cursor = db.cursor()

    # 1. Kiểm tra booking có tồn tại và thuộc user hiện tại không
    booking_query = """
        SELECT BookingId, HotelId, BookingStatus, CheckOutDate, ActualCheckOutTime
        FROM Bookings
        WHERE BookingId = ?
          AND UserId = ?
    """
    cursor.execute(booking_query, (payload.booking_id, user_id))
    booking_row = cursor.fetchone()

    if not booking_row:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy booking của user này"
        )

    booking_id = booking_row[0]
    hotel_id = booking_row[1]
    booking_status = booking_row[2]
    check_out_date = booking_row[3]
    actual_check_out_time = booking_row[4]

    # 2. Chỉ cho review khi booking đã confirmed
    if booking_status != "Confirmed":
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ được đánh giá booking đã xác nhận"
        )

    # 3. Chỉ cho review sau khi đã check-out
    review_allowed = False

    if actual_check_out_time is not None:
        review_allowed = True
    elif check_out_date is not None:
        cursor.execute("SELECT CAST(GETDATE() AS DATE)")
        today = cursor.fetchone()[0]
        if check_out_date < today:
            review_allowed = True

    if not review_allowed:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ được đánh giá sau khi hoàn thành thời gian lưu trú"
        )

    # 4. Kiểm tra booking này đã được review chưa
    existed_review_query = """
        SELECT TOP 1 ReviewId
        FROM Reviews
        WHERE BookingId = ?
    """
    cursor.execute(existed_review_query, (booking_id,))
    existed_review = cursor.fetchone()

    if existed_review:
        cursor.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking này đã được đánh giá rồi"
        )

    # 5. Insert review
    insert_query = """
        INSERT INTO Reviews (
            BookingId,
            UserId,
            HotelId,
            Rating,
            Comment,
            CreatedAt,
            Status
        )
        VALUES (?, ?, ?, ?, ?, GETDATE(), ?)`
    """
    cursor.execute(
        insert_query,
        (
            booking_id,
            user_id,
            hotel_id,
            payload.rating,
            payload.comment,
            "Active"
        )
    )

    db.commit()

    # 6. Lấy review_id vừa tạo
    cursor.execute("SELECT SCOPE_IDENTITY()")
    review_id = int(cursor.fetchone()[0])

    cursor.close()

    return {
        "message": "Đánh giá thành công",
        "review_id": review_id,
        "booking_id": booking_id,
        "hotel_id": hotel_id,
        "user_id": user_id
    }

