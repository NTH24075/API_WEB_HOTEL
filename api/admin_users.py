from fastapi import APIRouter, Depends, HTTPException
from core.database import get_conn
from core.dependencies import require_admin
from schemas.users_schemas import AdminCreateStaffRequest,AdminUpdateRoleRequest,AdminUpdateStatusRequest
router = APIRouter(prefix="/admin", tags=["Admin"])

def get_role_id_by_name(cursor, role_name:str):
    cursor.execute("select RoleId from Roles where RoleName = ?",(role_name,))
    row = cursor.fetchone()
    return row.RoleId if row else None

@router.get("/users")
def get_all_users(admin=Depends(require_admin)):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("select u.UserId,u.FullName,u.Email,u.Phone,u.CitizenId,u.Address,u.AvatarUrl,u.Status,u.CreatedAt,u.UpdatedAt,r.RoleName " \
                    "from Users u " \
                    "join Roles r ON u.RoleId = r.RoleId " \
                    "order by u.UserId desc ")
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                "user_id": row.UserId,
                "full_name": row.FullName,
                "email": row.Email,
                "phone": row.Phone,
                "citizen_id": row.CitizenId,
                "address": row.Address,
                "avatar_url": row.AvatarUrl,
                "status": row.Status,
                "created_at": str(row.CreatedAt),
                "updated_at": str(row.UpdatedAt) if row.UpdatedAt else None,
                "role_name": row.RoleName})
        return results
    finally:
        conn.close()

@router.post("/staff")
def admin_create_staff(data: AdminCreateStaffRequest, admin=Depends(require_admin)):
    if data.role_name not in ["Receptionist", "Admin"]:
        raise HTTPException(
            status_code=400,
            detail="Admin chi duoc tao tai khoan nhan vien: Receptionist hoặc Admin"
        )

    if data.status not in ["Active", "Inactive", "Blocked"]:
        raise HTTPException(status_code=400, detail="Status khong hop le")

    conn = get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT UserId FROM Users WHERE Email = ? ", (data.email,))
        existed = cursor.fetchone()
        if existed:
            raise HTTPException(status_code=400, detail="Email da ton tai")

        role_id = get_role_id_by_name(cursor, data.role_name)
        if not role_id:
            raise HTTPException(status_code=400, detail="Role khong ton tai")
        cursor.execute("insert into Users (RoleId, FullName, Email, Phone, PasswordHash, CitizenId, Address, AvatarUrl, Status) " \
                    "values(?, ?, ?, ?, ?, ?, ?, ?, ?) ", 
                    (role_id,
                    data.full_name,
                    data.email,
                    data.phone,
                    data.password,  # tạm thời plaintext
                    data.citizen_id,
                    data.address,
                    data.avatar_url,
                    data.status))
        conn.commit()
        return {"message": "Admin tạo tài khoản nhân viên thành công"}
    finally:
        conn.close()

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    data: AdminUpdateRoleRequest,
    admin=Depends(require_admin)
):
    if data.role_name not in ["Guest", "Receptionist", "Admin"]:
        raise HTTPException(status_code=400, detail="Role khong hop le")

    conn = get_conn()
    try:
        cursor = conn.cursor()

        role_id = get_role_id_by_name(cursor, data.role_name)
        if not role_id:
            raise HTTPException(status_code=400, detail="Role khong ton tai")

        cursor.execute("update Users " \
                    "set RoleId =?, UpdatedAt = GETDATE() " \
                    "where UserId = ? ", (role_id, user_id))
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="khong tim thay user")

        return {"message": "Cap nhap role thanh cong"}
    finally:
        conn.close()


@router.put("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    data: AdminUpdateStatusRequest,
    admin=Depends(require_admin)
):
    if data.status not in ["Active", "Inactive", "Blocked"]:
        raise HTTPException(status_code=400, detail="Status khong hop le")

    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(" update Users " \
                        "set Status = ?, UpdatedAt = GETDATE() " \
                        "where UserId = ? ", (data.status, user_id))
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Khong tim thay user")

        return {"message": "Cap nhap status thanh cong"}
    finally:
        conn.close()

@router.put("/delete-request/{request_id}/approve")
def approve_delete(request_id:int , admin = Depends(require_admin)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute("select UserId from DeleteAccountRequests " \
                    "where RequestId = ? and Status = 'Pending' ",(request_id,))
        row=curs.fetchone()
        if not row:
            raise HTTPException(404,"Request is not available")
        user_id = row.UserId

        #delte user
        curs.execute("update Users " \
                    "set Status = 'Deleted', UpdatedAt = getdate() " \
                    "where UserId = ? ",(user_id,))

        #done request
        curs.execute("update DeleteAccountRequests " \
                    "set Status = 'Approved', ProcessedAt = getdate() " \
                    "where RequestId = ? ",(request_id,))
        conn.commit()
        return {"message":"Da xoa thanh cong tai khoan"}
    finally:
        conn.close()

@router.get("/update-logs")
def get_update_logs(admin=Depends(require_admin)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute(
            "select ul.LogId, ul.UserId, ul.UpdatedAt, u.FullName "
            "from UserUpdateLogs ul "
            "join Users u on ul.UserId = u.UserId "
            "order by ul.LogId desc"
        )
        rows = curs.fetchall()

        results = []
        for row in rows:
            results.append({
                "log_id": row.LogId,
                "user_id": row.UserId,
                "full_name": row.FullName,
                "updated_at": str(row.UpdatedAt)
            })
        return results
    finally:
        conn.close()

@router.get("/delete-requests")
def get_delete_requests(admin=Depends(require_admin)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute(
            "select dr.RequestId, dr.UserId, dr.Status, dr.CreatedAt, dr.ProcessedAt, u.FullName "
            "from DeleteAccountRequests dr "
            "join Users u on dr.UserId = u.UserId "
            "order by dr.RequestId desc"
        )
        rows = curs.fetchall()

        results = []
        for row in rows:
            results.append({
                "request_id": row.RequestId,
                "user_id": row.UserId,
                "full_name": row.FullName,
                "status": row.Status,
                "created_at": str(row.CreatedAt),
                "processed_at": str(row.ProcessedAt) if row.ProcessedAt else None
            })
        return results
    finally:
        conn.close()

@router.get("/delete-requests/{request_id}")
def get_delete_request_detail(request_id: int, admin=Depends(require_admin)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute(
            "select dr.RequestId, dr.UserId, dr.Status, dr.Reason, "
            "u.FullName, u.Email, u.Phone, u.CitizenId, u.Address, u.Status as UserStatus, r.RoleName "
            "from DeleteAccountRequests dr "
            "join Users u on dr.UserId = u.UserId "
            "join Roles r on u.RoleId = r.RoleId "
            "where dr.RequestId = ?",
            (request_id,)
        )
        row = curs.fetchone()

        if not row:
            raise HTTPException(404, "Khong tim thay request")

        return {
            "request_id": row.RequestId,
            "user_id": row.UserId,
            "request_status": row.Status,
            "reason": row.Reason,
            "user": {
                "full_name": row.FullName,
                "email": row.Email,
                "phone": row.Phone,
                "citizen_id": row.CitizenId,
                "address": row.Address,
                "status": row.UserStatus,
                "role_name": row.RoleName
            }
        }
    finally:
        conn.close()

@router.put("/delete-request/{request_id}/reject")
def reject_delete(request_id: int, admin=Depends(require_admin)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute(
            "update DeleteAccountRequests "
            "set Status = 'Rejected', ProcessedAt = GETDATE() "
            "where RequestId = ? and Status = 'Pending'",
            (request_id,)
        )
        conn.commit()

        if curs.rowcount == 0:
            raise HTTPException(404, "Request khong hop le")

        return {"message": "Da reject request"}
    finally:
        conn.close()