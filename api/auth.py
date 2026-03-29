from fastapi import APIRouter, Depends, HTTPException
from core.database import get_conn
from services.auth_utils import create_access_token
from core.dependencies import get_current_user
from schemas.users_schemas import RegisterRequest, LoginRequest, TokenResponse
router = APIRouter(prefix="/auth", tags=["Auth"])

def get_role_id_by_name(curs, role_name:str):
    curs.execute("Select RoleId from Roles where RoleName = ?",(role_name,))
    row = curs.fetchone()
    return row.RoleId if row else None

@router.post("/register", response_model=TokenResponse)
def register(data: RegisterRequest):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute("select UserId from Users where Email = ?",(data.email,))
        existed = curs.fetchone()
        if existed:
            raise HTTPException(status_code=400, detail="Email da ton tai")
        guest_role_id = get_role_id_by_name(curs, "Guest")
        if not guest_role_id:
            raise HTTPException(
                status_code=400,
                detail="Role 'Guest' chua ton tai trong he thong"
            )
        curs.execute("insert into Users(RoleId,FullName,Email,Phone,PasswordHash,CitizenId,Address,AvatarUrl,Status) " \
                    "output inserted.UserId " \
                    "values(?,?,?,?,?,?,?,?,?)",(guest_role_id,
                                                 data.full_name,
                                                 data.email,
                                                 data.phone,
                                                 data.password,
                                                 data.citizen_id,
                                                 data.address,
                                                 data.avatar_url,
                                                 "Active"))
        new_user = curs.fetchone()
        conn.commit()
        curs.execute(
                    "select u.UserId, u.FullName, u.Email, u.Phone, u.CitizenId, "
                    "u.Address, u.AvatarUrl, u.Status, r.RoleName "
                    "from Users u "
                    "join Roles r ON u.RoleId = r.RoleId "
                    "where u.UserId = ? ",
                    (new_user.UserId,)
)
        row = curs.fetchone()
        token = create_access_token({"user_id":row.UserId, "email":row.Email,"role_name":row.RoleName})
        return {
            "access_token":token,
            "token_type":"bearer",
            "user":{
                "user_id":row.UserId,
                "full_name":row.FullName,
                "email":row.Email,
                "phone":row.Phone,
                "citizen_id":row.CitizenId,
                "address":row.Address,
                "avatar_url": row.AvatarUrl,
                "role_name": row.RoleName,
                "status": row.Status
            }
        }
    finally:
        conn.close()

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute("select u.UserId,u.FullName,u.Email,u.Phone,u.CitizenId,u.Address,u.AvatarUrl,u.PasswordHash,u.Status,r.RoleName " \
                    "from Users u " \
                    "join Roles r ON u.RoleId = r.RoleId " \
                    "where u.Email = ? ",(data.email,))
        row = curs.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Sai email hoac mat khau")
        
        if row.PasswordHash != data.password:
            raise HTTPException(status_code=401, detail="Sai email hoac mat khau")

        if row.Status != "Active":
            raise HTTPException(
                status_code=403,
                detail=f"Tài khoản đang ở trạng thái {row.Status}"
            )
        token = create_access_token({
            "user_id":row.UserId,
            "email":row.Email,
            "role_name":row.RoleName
        })
        return {
            "access_token": token,
            "token_type": "bearer",
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

@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return current_user