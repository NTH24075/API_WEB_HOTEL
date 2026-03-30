from fastapi import APIRouter, HTTPException, Depends
from core.database import get_conn
from core.dependencies import get_current_user
from schemas.users_schemas import UpdateAccountInfoRequest

router = APIRouter(prefix="/user", tags=["User"])

@router.post("/delete-request")
def request_delete_account(cur_user=Depends(get_current_user)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute("select 1 from DeleteAccountRequests " \
                    "where UserId = ? and Status = 'Pending' ",(cur_user["user_id"],))
        existed = curs.fetchone()
        if existed:
            raise HTTPException(400,"Ban da gui yeu cau truoc do")
        curs.execute("insert into DeleteAccountRequests(UserId, Status) " \
                    "values (?, 'Pending')", (cur_user["user_id"],))
        conn.commit()
        return {"message":"Da gui yeu cau xoa tai khoan"}
    finally:
        conn.close()
        
@router.put("/me")
def update_account_info(data: UpdateAccountInfoRequest ,cur_user=Depends(get_current_user)):
    conn = get_conn()
    try:
        curs = conn.cursor()
        #check info account
        curs.execute("select UserId, Status from Users where UserId = ?",(cur_user["user_id"],))
        exixted = curs.fetchone()

        if not exixted:
            raise HTTPException(404, "Khong tim thay thong tin user")
        
        if exixted.Status != "Active":
            raise HTTPException(403,f"Tai khoan dang o trang thai {exixted.Status}")
        
        #update info
        curs.execute("update Users "
                    "set FullName = ?, "
                    "    Phone = ?, "
                    "    CitizenId = ?, "
                    "    Address = ?, "
                    "    AvatarUrl = ?, "
                    "    UpdatedAt = GETDATE() "
                    "where UserId = ?",(data.full_name, data.phone, data.citizen_id, data.address, data.avatar_url,cur_user["user_id"]))
        conn.commit()
        curs.execute("select u.UserId, u.FullName, u.Email, u.Phone, u.CitizenId, u.Address, u.AvatarUrl, u.Status, r.RoleName "
                    "from Users u "
                    "join Roles r on u.RoleId = r.RoleId "
                    "where u.UserId = ?",(cur_user["user_id"],))
        row = curs.fetchone()
        return {
            "message": "Cap nhat thong tin ca nhan thanh cong",
            "user": {
                "user_id": row.UserId,
                "full_name": row.FullName,
                "email": row.Email,
                "phone": row.Phone,
                "citizen_id": row.CitizenId,
                "address": row.Address,
                "avatar_url": row.AvatarUrl,
                "role_name": row.RoleName,
                "status": row.Status
            }
        }
    finally:
        conn.close()