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


hotel_router = APIRouter(prefix="/api/bookinghotels", tags=["Hotels"])


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
    service_items: list[dict],  # [ {"service_id": 1, "quantity": 1}, {"service_id": 2, "quantity": 1}, {"service_id": 3, "quantity": 1}]
    db=Depends(get_conn),
    current_user: dict = Depends(get_current_user)
):
    cursor = db.cursor()

    try:
        # 1. Check booking tồn tại
        cursor.execute("""
            SELECT TotalAmount
            FROM Bookings
            WHERE BookingId = ?
        """, (booking_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Booking không tồn tại")

        current_total = float(row[0])
        total_service_cost = 0
        added_services = []

        # 2. Validate danh sách service
        if not service_items or not isinstance(service_items, list):
            raise HTTPException(
                status_code=400,
                detail="service_items phải là một danh sách, ví dụ: [{'service_id': 1, 'quantity': 2}]"
            )

        # 3. Loop từng service
        for index, item in enumerate(service_items, start=1):
            if not isinstance(item, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"Phần tử thứ {index} không hợp lệ, phải là object"
                )

            service_id = item.get("service_id")
            quantity = item.get("quantity", 1)

            if service_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Thiếu service_id ở phần tử thứ {index}"
                )

            if quantity is None:
                quantity = 1

            try:
                service_id = int(service_id)
                quantity = int(quantity)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"service_id hoặc quantity ở phần tử thứ {index} không đúng kiểu số"
                )

            if quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"quantity ở phần tử thứ {index} phải lớn hơn 0"
                )

            # lấy thông tin service
            cursor.execute("""
                SELECT Price
                FROM Services
                WHERE ServiceId = ? AND IsActive = 1
            """, (service_id,))
            
            service = cursor.fetchone()
            if not service:
                raise HTTPException(
                    status_code=404,
                    detail=f"Không tìm thấy service_id = {service_id} hoặc dịch vụ đã bị khóa"
                )

            unit_price = float(service[0])
            total_price = unit_price * quantity

            # insert BookingServices
            cursor.execute("""
                INSERT INTO BookingServices (
                    BookingId,
                    ServiceId,
                    Quantity,
                    UnitPrice,
                    TotalPrice,
                    UsedAt
                )
                VALUES (?, ?, ?, ?, ?, NULL)
            """, (
                booking_id,
                service_id,
                quantity,
                unit_price,
                total_price
            ))

            total_service_cost += total_price
            added_services.append({
                "service_id": service_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price
            })

        # 4. Update lại Booking
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
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
    finally:
        cursor.close()

    # ========================
    # 3. Update lại Booking
    # ========================
    new_total = current_total + total_service_cost

    cursor.execute("""
        UPDATE Bookings
        SET TotalAmount = ?
        WHERE BookingId = ?
    """, (new_total, booking_id))

    db.commit()
    cursor.close()

    return {
        "message": "Thêm dịch vụ thành công",
        "booking_id": booking_id,
        "added_service_cost": total_service_cost,
        "new_total_amount": new_total
    }

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
            "Paid"
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
            "Paid",
            "Confirmed",
            booking_id
        ))

        db.commit()

        return {
            "message": "Thanh toán thành công",
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