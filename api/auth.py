from fastapi import APIRouter, Depends, HTTPException
from core.database import get_conn
from services.auth_utils import create_access_token
from core.dependencies import get_current_user
from google.oauth2 import id_token
from google.auth.transport import requests
from schemas.users_schemas import RegisterRequest, LoginRequest, TokenResponse, GoogleAuthRequest
import secrets
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Get role id bằng role name
def get_role_id_by_name(curs, role_name:str):
    curs.execute("Select RoleId from Roles where RoleName = ?",(role_name,))
    row = curs.fetchone()
    return row.RoleId if row else None

# kiểm tra token google
def verify_google_token(credentials: str):
    try:
        info = id_token.verify_oauth2_token(credentials, requests.Request(), GOOGLE_CLIENT_ID)
        if info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid issuer")
        return info
    except Exception:
        return None
    
@router.post("/google", response_model=TokenResponse)
def google_auth(data: GoogleAuthRequest):

    #random password for gg acount
    random_pwd_f_gg_accounts = secrets.token_urlsafe(32)

    google_info = verify_google_token(data.credential)
    if not google_info:
        raise HTTPException(status_code=401, detail="Google token khong hop le")
    if not google_info.get("email_verified",False):
        raise HTTPException(400, "Email Google chua duoc xac minh")
    
    google_sub = google_info.get("sub")
    email = google_info.get("email")
    full_name = google_info.get("name") or "Google User"
    avatar_url = google_info.get("picture")

    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Khong lay duoc thong tin tu Google")

    conn = get_conn()
    try:
        curs = conn.cursor()

        # tìm theo gg sub
        curs.execute("select u.UserId,u.FullName,u.Email,u.Phone,u.CitizenId,u.Address,u.AvatarUrl,u.Status,r.RoleName "
            "from Users u "
            "join Roles r ON u.RoleId = r.RoleId "
            "where u.GoogleSub = ? ",(google_sub,))
        row = curs.fetchone()

        # nếu chưa có GoogleSub thì tìm theo email để link chung 1 tài khoản
        if not row:
            curs.execute("select UserId, FullName, Email, Phone, CitizenId, Address, AvatarUrl, Status, RoleId "
                "from Users where Email = ? ",(email,))
            email_user = curs.fetchone()

            if email_user:
                # link tài khoản cũ với Google
                curs.execute("update Users "
                    "set GoogleSub = ?, UpdatedAt = GETDATE(), AvatarUrl = ISNULL(AvatarUrl, ?) "
                    "where UserId = ? ",(google_sub, avatar_url, email_user.UserId))
                conn.commit()

                curs.execute("select u.UserId,u.FullName,u.Email,u.Phone,u.CitizenId,u.Address,u.AvatarUrl,u.Status,r.RoleName "
                    "from Users u "
                    "join Roles r ON u.RoleId = r.RoleId "
                    "where u.UserId = ? ",(email_user.UserId,))
                row = curs.fetchone()

        # nếu chưa có luôn thì tạo user mới
        if not row:
            guest_role_id = get_role_id_by_name(curs, "Guest")
            if not guest_role_id:
                raise HTTPException(status_code=400, detail="Role 'Guest' chua ton tai")
            curs.execute("insert into Users(RoleId, FullName, Email, Phone, PasswordHash, CitizenId, Address, AvatarUrl, Status, GoogleSub) "
                "output inserted.UserId "
                "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                ,(guest_role_id,full_name,email,None,random_pwd_f_gg_accounts,None,None,avatar_url,"Active",google_sub))
            new_user = curs.fetchone()
            conn.commit()

            curs.execute("select u.UserId,u.FullName,u.Email,u.Phone,u.CitizenId,u.Address,u.AvatarUrl,u.Status,r.RoleName "
                "from Users u "
                "join Roles r ON u.RoleId = r.RoleId "
                "where u.UserId = ? ",(new_user.UserId,))
            row = curs.fetchone()

        if row.Status != "Active":
            raise HTTPException(
                status_code=403,
                detail=f"Tai khoan dang o trang thai {row.Status}"
            )

        token = create_access_token({
            "user_id": row.UserId,
            "email": row.Email,
            "role_name": row.RoleName
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
        curs.execute("select u.UserId,u.FullName,u.Email,u.Phone,u.CitizenId,u.Address,u.AvatarUrl,u.Status,r.RoleName " \
                    "from Users u " \
                    "join Roles r ON u.RoleId = r.RoleId " \
                    "where UserId = ? ",(new_user.UserId,))
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
        curs.execute("select u.UserId,u.FullName,u.Email,u.Phone,u.CitizenId,u.Address,u.AvatarUrl,u.PasswordHash,u.Status,r.RoleName,u.GoogleSub " \
                    "from Users u " \
                    "join Roles r ON u.RoleId = r.RoleId " \
                    "where u.Email = ? ",(data.email,))
        row = curs.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Sai email hoac mat khau")
        if row.GoogleSub is not None:
            raise HTTPException(400, "Tai khoan cua ban dang nhap bang Google")
        if row.PasswordHash != data.password:
            raise HTTPException(status_code=401, detail="Sai email hoac mat khau")

        if row.Status != "Active":
            raise HTTPException(
                status_code=403,
                detail=f"Tai khoan dang o trang thai {row.Status}"
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

