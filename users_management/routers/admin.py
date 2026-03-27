from fastapi import APIRouter, Depends, HTTPException
from database import get_conn
from dependencies import require_admin
from schemas import AdminCreateStaffRequest, AdminUpdateRoleRequest, AdminUpdateStatusRequest

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