from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.database import get_conn
from services.auth_utils import decode_access_token

security = HTTPBearer()


def get_current_user(ycredentials:HTTPAuthorizationCredentials=Depends(security)):
    token = ycredentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Token khong hop le"
        )
    user_id = payload.get("user_id")
    conn = get_conn()
    try:
        curs = conn.cursor()
        curs.execute("select u.UserId, u.FullName, u.Email, u.Phone, u.CitizenId, u.Address, u.AvatarUrl, u.AvatarUrl, u.Status, r.RoleName " \
                    "from Users u " \
                    "join Roles r On u.RoleId = r.RoleId " \
                    "where u.UserId = ? ", (user_id,))
        row = curs.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Khong tim thay user")

        if row.Status != "Active":
            raise HTTPException(status_code=403,detail=f"Tai khoan dang o trang thai{row.Status}")
        return {
            "user_id":row.UserId,
            "full_name":row.FullName,
            "email": row.Email,
            "phone": row.Phone,
            "citizen_id": row.CitizenId,
            "address": row.Address,
            "avatar_url": row.AvatarUrl,
            "role_name": row.RoleName,
            "status": row.Status
        }
    finally:
        conn.close()

def require_admin(cur_user = Depends(get_current_user)):
    if cur_user["role_name"]!="Admin":
        raise HTTPException(
            status_code=403,
            detail="Chi Admin moi co quyen truy cap"
        )
    return cur_user
